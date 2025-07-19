import requests
import os
import tempfile
import uuid
import logging
try:
    from flask import current_app
except ImportError:
    current_app = None


class ChimegeTTS:
    """Chimege Mongolian Text-to-Speech API client"""
    
    def __init__(self):
        self.base_url = "https://api.chimege.com/v1.2"
        self.token = os.environ.get('CHIMEGE_API_TOKEN')
        
    def _log_info(self, message):
        """Log info message with fallback to print"""
        if current_app and hasattr(current_app, 'logger'):
            current_app.logger.info(f"CHIMEGE TTS: {message}")
        else:
            print(f"CHIMEGE TTS INFO: {message}")
    
    def _log_warning(self, message):
        """Log warning message with fallback to print"""
        if current_app and hasattr(current_app, 'logger'):
            current_app.logger.warning(f"CHIMEGE TTS: {message}")
        else:
            print(f"CHIMEGE TTS WARNING: {message}")
    
    def _log_error(self, message):
        """Log error message with fallback to print"""
        if current_app and hasattr(current_app, 'logger'):
            current_app.logger.error(f"CHIMEGE TTS: {message}")
        else:
            print(f"CHIMEGE TTS ERROR: {message}")
        
    def synthesize_text(self, text, voice_id="FEMALE3v2", speed=1.0, pitch=1.0, sample_rate=22050):
        """
        Convert text to speech using Chimege API
        
        Args:
            text (str): Text to convert (2-300 characters)
            voice_id (str): Voice to use (FEMALE1, FEMALE1v2, FEMALE2v2, FEMALE3v2, FEMALE4v2, FEMALE5v2, MALE1, MALE1v2, MALE2v2, MALE3v2, MALE4v2)
            speed (float): Speech speed (0.2-4.0)
            pitch (float): Voice pitch (0.2-6.0)
            sample_rate (int): Audio sample rate (8000, 16000, 22050)
            
        Returns:
            str: Path to generated audio file, or None if failed
        """
        
        if not self.token:
            self._log_error("Chimege API token not configured")
            return None
            
        if not text or len(text.strip()) < 2:
            self._log_error("Text too short for TTS")
            return None
            
        if len(text) > 300:
            self._log_warning("Text too long, truncating to 300 characters")
            text = text[:300]
            
        try:
            # Prepare request
            url = f"{self.base_url}/synthesize"
            headers = {
                'Content-Type': 'text/plain',
                'Token': self.token,
                'voice-id': voice_id,
                'speed': str(speed),
                'pitch': str(pitch),
                'sample-rate': str(sample_rate)
            }
            
            self._log_info(f"Making API request to: {url}")
            self._log_info(f"Headers: {headers}")
            self._log_info(f"Text to synthesize: '{text}'")
            
            # Make request
            response = requests.post(
                url, 
                data=text.encode('utf-8'), 
                headers=headers,
                timeout=30
            )
            
            self._log_info(f"API response status: {response.status_code}")
            self._log_info(f"API response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                # Save audio to temporary file
                audio_filename = f"tts_{uuid.uuid4().hex}.wav"
                audio_path = os.path.join(tempfile.gettempdir(), audio_filename)
                
                with open(audio_path, 'wb') as f:
                    f.write(response.content)
                
                self._log_info(f"TTS generated: {audio_path}")
                return audio_path
                
            else:
                error_code = response.headers.get('Error-Code', 'Unknown')
                self._log_error(f"Chimege API error {response.status_code}: {error_code}")
                return None
                
        except requests.RequestException as e:
            self._log_error(f"Chimege API request failed: {str(e)}")
            return None
        except Exception as e:
            self._log_error(f"TTS generation failed: {str(e)}")
            return None
            
    def normalize_text(self, text):
        """
        Normalize text for better TTS pronunciation
        
        Args:
            text (str): Raw text to normalize
            
        Returns:
            str: Normalized text, or original if failed
        """
        
        if not self.token:
            return text
            
        try:
            url = f"{self.base_url}/normalize-text"
            headers = {
                'Content-Type': 'text/plain',
                'Token': self.token
            }
            
            response = requests.post(
                url, 
                data=text.encode('utf-8'), 
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                normalized = response.content.decode('utf-8')
                self._log_info(f"Text normalized: '{text}' -> '{normalized}'")
                return normalized
            else:
                self._log_warning(f"Text normalization failed: {response.status_code}")
                return text
                
        except Exception as e:
            self._log_error(f"Text normalization error: {str(e)}")
            return text
            
    def get_available_voices(self):
        """Get list of available voices"""
        return {
            'female': ['FEMALE1', 'FEMALE1v2', 'FEMALE2v2', 'FEMALE3v2', 'FEMALE4v2', 'FEMALE5v2'],
            'male': ['MALE1', 'MALE1v2', 'MALE2v2', 'MALE3v2', 'MALE4v2']
        }
        
    def cleanup_temp_file(self, file_path):
        """Clean up temporary audio file"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                self._log_info(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            self._log_error(f"Failed to cleanup temp file: {str(e)}")