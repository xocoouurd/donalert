"""
QuickPay Payment Integration Utility for DonAlert
Handles authentication, invoice creation, and payment processing for subscription payments
"""

import os
import requests
import base64
import json
from datetime import datetime, timedelta
from flask import current_app, url_for
from app.models.user import User
from app.models.subscription import Subscription
from app.extensions import db

class QuickPayClient:
    """QuickPay API client for subscription payment processing"""
    
    def __init__(self):
        self.base_url = os.getenv('QPAYQUICKQR_URL')
        self.username = os.getenv('QPAYQUICKQR_USERNAME')
        self.password = os.getenv('QPAYQUICKQR_PASSWORD')
        self.terminal_id = os.getenv('QPAYQUICKQR_TERMINAL_ID')
        self.merchant_id = os.getenv('QPAYQUICKQR_MERCHANT_ID')
        self.bank_iban = os.getenv('BANK_IBAN')
        self.bank_code = os.getenv('BANK_CODE')
        self.bank_account_name = os.getenv('BANK_ACCOUNT_NAME')
        
        # Current token will be managed in-memory for now
        self.current_token = None
        self.token_expires_at = None
    
    def get_valid_token(self):
        """
        Get valid access token with simple in-memory management
        Returns valid access token or None if authentication fails
        """
        try:
            # Check if we have a valid token
            if (self.current_token and self.token_expires_at and 
                datetime.now() < self.token_expires_at - timedelta(minutes=5)):
                return self.current_token
            
            # Need to authenticate
            return self._authenticate()
            
        except Exception as e:
            current_app.logger.error(f"QuickPay token management error: {str(e)}")
            return self._authenticate()
    
    def _authenticate(self):
        """Perform authentication and get new token"""
        try:
            url = f"{self.base_url}/v2/auth/token"
            
            # Basic Auth credentials
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "terminal_id": self.terminal_id
            }
            
            current_app.logger.info("QuickPay: Authenticating...")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                self.current_token = token_data['access_token']
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                current_app.logger.info("QuickPay: Authentication successful")
                return self.current_token
            else:
                current_app.logger.error(f"QuickPay authentication failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"QuickPay authentication network error: {str(e)}")
            return None
        except Exception as e:
            current_app.logger.error(f"QuickPay authentication error: {str(e)}")
            return None
    
    def ensure_authenticated(self):
        """Ensure we have a valid access token"""
        token = self.get_valid_token()
        return token is not None
    
    def create_subscription_invoice(self, user_id, tier, months=1):
        """
        Create QuickPay invoice for subscription payment
        
        Args:
            user_id: ID of the user
            tier: Subscription tier ('basic', 'premium', 'enterprise')
            months: Number of months (default 1)
            
        Returns:
            dict: Invoice response or error dict
        """
        try:
            # Get valid access token
            access_token = self.get_valid_token()
            if not access_token:
                return {"error": "Authentication failed", "success": False}
            
            # Get user information
            user = User.query.get(user_id)
            if not user:
                return {"error": "User not found", "success": False}
            
            # Calculate subscription cost
            subscription_cost = Subscription.calculate_subscription_cost(tier, months)
            if not subscription_cost:
                return {"error": "Invalid subscription tier or months", "success": False}
            
            # Create customer name
            customer_name = user.get_display_name() or f"User {user_id}"
            
            # Create description
            tier_names = {
                'basic': 'Үндсэн',
                'premium': 'Дэвшилтэт', 
                'enterprise': 'Байгууллагын'
            }
            tier_display = tier_names.get(tier, tier)
            
            if months == 1:
                description = f"DonAlert - {tier_display} багц (1 сар)"
            elif months == 3:
                description = f"DonAlert - {tier_display} багц (3 сар)"
            elif months == 6:
                description = f"DonAlert - {tier_display} багц (6 сар)"
            elif months == 12:
                description = f"DonAlert - {tier_display} багц (12 сар)"
            else:
                description = f"DonAlert - {tier_display} багц ({months} сар)"
            
            # Create secure callback URL
            import secrets
            webhook_token = secrets.token_urlsafe(32)
            
            # Create callback URL
            try:
                callback_url = url_for('main.subscription_callback', token=webhook_token, _external=True)
            except (RuntimeError, Exception):
                # Fallback for when not in request context
                server_name = os.getenv('SERVER_NAME', 'donalert.invictamotus.com')
                callback_url = f"https://{server_name}/subscription/callback?token={webhook_token}"
            
            # Extract account number from IBAN (last 10 digits)
            account_number = self.bank_iban[-10:] if self.bank_iban else "1205284753"
            
            # Create invoice payload
            payload = {
                "merchant_id": self.merchant_id,
                "terminal_id": self.terminal_id,
                "amount": int(subscription_cost),
                "currency": "MNT",
                "branch_code": "DONALERT_SUB",
                "customer_name": customer_name,
                "customer_logo": "",
                "description": description,
                "callback_url": callback_url,
                "mcc_code": "7372",  # Computer and Data Processing Services
                "bank_accounts": [
                    {
                        "default": True,
                        "account_bank_code": self.bank_code,
                        "account_number": account_number,
                        "account_name": self.bank_account_name,
                        "account_iban": self.bank_iban,
                        "is_default": True
                    }
                ]
            }
            
            # Send invoice creation request
            url = f"{self.base_url}/v2/invoice"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            current_app.logger.info(f"QuickPay: Creating subscription invoice for user {user_id}, tier: {tier}, months: {months}, amount: {subscription_cost}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                invoice_data = response.json()
                
                current_app.logger.info(f"QuickPay: Subscription invoice created successfully - ID: {invoice_data.get('id')}")
                
                # Prepare response data
                response_data = {
                    "success": True,
                    "invoice_id": invoice_data.get('id'),
                    "qr_code": invoice_data.get('qr_code'),
                    "qr_image": invoice_data.get('qr_image'),
                    "amount": int(subscription_cost),
                    "currency": "MNT",
                    "customer_name": customer_name,
                    "description": description,
                    "app_links": invoice_data.get('urls', []),
                    "payment_url": invoice_data.get('payment_url'),
                    "webhook_token": webhook_token,
                    "tier": tier,
                    "months": months,
                    "callback_url": callback_url,
                    "raw_response": invoice_data
                }
                
                return response_data
            else:
                current_app.logger.error(f"QuickPay subscription invoice creation failed: {response.status_code} - {response.text}")
                return {
                    "error": f"Invoice creation failed: {response.status_code}",
                    "success": False,
                    "details": response.text
                }
                
        except Exception as e:
            current_app.logger.error(f"QuickPay subscription invoice creation error: {str(e)}")
            return {
                "error": f"Invoice creation error: {str(e)}",
                "success": False
            }
    
    def check_payment_status(self, invoice_id):
        """
        Check payment status for an invoice
        
        Args:
            invoice_id: QuickPay invoice ID
            
        Returns:
            dict: Payment status response
        """
        try:
            access_token = self.get_valid_token()
            if not access_token:
                return {"error": "Authentication failed", "success": False}
            
            url = f"{self.base_url}/v2/payment/check"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "invoice_id": invoice_id
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                payment_data = response.json()
                current_app.logger.info(f"QuickPay: Payment status check successful for invoice {invoice_id}")
                return {"success": True, "data": payment_data}
            else:
                current_app.logger.error(f"QuickPay payment check failed: {response.status_code} - {response.text}")
                return {"error": f"Payment check failed: {response.status_code}", "success": False}
                
        except Exception as e:
            current_app.logger.error(f"QuickPay payment status check error: {str(e)}")
            return {"error": f"Payment check error: {str(e)}", "success": False}
    
    def get_invoice_details(self, invoice_id):
        """
        Get invoice details
        
        Args:
            invoice_id: QuickPay invoice ID
            
        Returns:
            dict: Invoice details response
        """
        try:
            access_token = self.get_valid_token()
            if not access_token:
                return {"error": "Authentication failed", "success": False}
            
            url = f"{self.base_url}/v2/invoice/{invoice_id}"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                invoice_data = response.json()
                current_app.logger.info(f"QuickPay: Invoice details retrieved for {invoice_id}")
                return {"success": True, "data": invoice_data}
            else:
                current_app.logger.error(f"QuickPay invoice details failed: {response.status_code} - {response.text}")
                return {"error": f"Invoice details failed: {response.status_code}", "success": False}
                
        except Exception as e:
            current_app.logger.error(f"QuickPay invoice details error: {str(e)}")
            return {"error": f"Invoice details error: {str(e)}", "success": False}
    
    def create_donation_invoice(self, streamer_user_id, donor_name, amount, message=""):
        """
        Create QuickPay invoice for donation payment using streamer's bank account
        
        Args:
            streamer_user_id: ID of the streamer receiving the donation
            donor_name: Name of the donor
            amount: Donation amount in MNT
            message: Optional donation message
            
        Returns:
            dict: Invoice response or error dict
        """
        try:
            # Get valid access token
            access_token = self.get_valid_token()
            if not access_token:
                return {"error": "Authentication failed", "success": False}
            
            # Get streamer information
            streamer = User.query.get(streamer_user_id)
            if not streamer:
                return {"error": "Streamer not found", "success": False}
            
            # Check if streamer has bank account setup
            if not streamer.bank_iban or not streamer.bank_account_name:
                return {"error": "Streamer bank account not configured", "success": False}
            
            # Validate amount
            if amount <= 0:
                return {"error": "Invalid donation amount", "success": False}
            
            # Create customer name (donor)
            customer_name = donor_name or "Anonymous Donor"
            
            # Create description
            streamer_name = streamer.get_display_name()
            if message:
                description = f"Donation to {streamer_name}: {message}"
            else:
                description = f"Donation to {streamer_name}"
            
            # Create secure callback URL
            import secrets
            webhook_token = secrets.token_urlsafe(32)
            
            # Create callback URL
            try:
                callback_url = url_for('main.donation_callback', token=webhook_token, _external=True)
            except (RuntimeError, Exception):
                # Fallback for when not in request context
                server_name = os.getenv('SERVER_NAME', 'donalert.invictamotus.com')
                callback_url = f"https://{server_name}/donation/callback?token={webhook_token}"
            
            # Extract account number from streamer's IBAN (last 10 digits)
            account_number = streamer.bank_iban[-10:] if streamer.bank_iban else ""
            
            # Create invoice payload with streamer's bank account
            payload = {
                "merchant_id": self.merchant_id,
                "terminal_id": self.terminal_id,
                "amount": int(amount),
                "currency": "MNT",
                "branch_code": "DONALERT_DONATION",
                "customer_name": customer_name,
                "customer_logo": "",
                "description": description,
                "callback_url": callback_url,
                "mcc_code": "7372",  # Computer and Data Processing Services
                "bank_accounts": [
                    {
                        "default": True,
                        "account_bank_code": streamer.bank_code,
                        "account_number": account_number,
                        "account_name": streamer.bank_account_name,
                        "account_iban": streamer.bank_iban,
                        "is_default": True
                    }
                ]
            }
            
            # Send invoice creation request
            url = f"{self.base_url}/v2/invoice"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            current_app.logger.info(f"QuickPay: Creating donation invoice for streamer {streamer_user_id}, amount: {amount}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                invoice_data = response.json()
                
                current_app.logger.info(f"QuickPay: Donation invoice created successfully - ID: {invoice_data.get('id')}")
                
                # Prepare response data
                response_data = {
                    "success": True,
                    "invoice_id": invoice_data.get('id'),
                    "qr_code": invoice_data.get('qr_code'),
                    "qr_image": invoice_data.get('qr_image'),
                    "amount": int(amount),
                    "currency": "MNT",
                    "customer_name": customer_name,
                    "description": description,
                    "app_links": invoice_data.get('urls', []),
                    "payment_url": invoice_data.get('payment_url'),
                    "webhook_token": webhook_token,
                    "callback_url": callback_url,
                    "streamer_id": streamer_user_id,
                    "donor_name": donor_name,
                    "message": message,
                    "raw_response": invoice_data
                }
                
                return response_data
            else:
                current_app.logger.error(f"QuickPay donation invoice creation failed: {response.status_code} - {response.text}")
                return {
                    "error": f"Invoice creation failed: {response.status_code}",
                    "success": False,
                    "details": response.text
                }
                
        except Exception as e:
            current_app.logger.error(f"QuickPay donation invoice creation error: {str(e)}")
            return {
                "error": f"Invoice creation error: {str(e)}",
                "success": False
            }

# Global client instance
quickpay_client = QuickPayClient()

def create_subscription_invoice(user_id, tier, months=1):
    """
    Convenience function to create subscription invoice
    
    Args:
        user_id: ID of the user
        tier: Subscription tier ('basic', 'premium', 'enterprise')
        months: Number of months (default 1)
        
    Returns:
        dict: Invoice response or error dict
    """
    return quickpay_client.create_subscription_invoice(user_id, tier, months)

def check_subscription_payment_status(invoice_id):
    """
    Check payment status for a subscription invoice
    
    Args:
        invoice_id: QuickPay invoice ID
        
    Returns:
        dict: Payment status response
    """
    return quickpay_client.check_payment_status(invoice_id)

def get_subscription_invoice_details(invoice_id):
    """
    Get subscription invoice details
    
    Args:
        invoice_id: QuickPay invoice ID
        
    Returns:
        dict: Invoice details response
    """
    return quickpay_client.get_invoice_details(invoice_id)

def create_donation_invoice(streamer_user_id, donor_name, amount, message=""):
    """
    Convenience function to create donation invoice
    
    Args:
        streamer_user_id: ID of the streamer receiving the donation
        donor_name: Name of the donor
        amount: Donation amount in MNT
        message: Optional donation message
        
    Returns:
        dict: Invoice response or error dict
    """
    return quickpay_client.create_donation_invoice(streamer_user_id, donor_name, amount, message)

# Bank logos are now loaded from static JSON file
# Use fetch_bank_logos.py script to update the logos if needed