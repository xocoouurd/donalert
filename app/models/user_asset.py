from app.extensions import db
from datetime import datetime
from werkzeug.utils import secure_filename
import os

class UserAsset(db.Model):
    __tablename__ = 'user_assets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asset_type = db.Column(db.String(20), nullable=False)  # 'gif', 'sound'
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # in bytes
    mime_type = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('assets', lazy=True, cascade='all, delete-orphan'))
    
    def __init__(self, user_id, asset_type, original_filename, stored_filename, display_name, file_size, mime_type):
        self.user_id = user_id
        self.asset_type = asset_type
        self.original_filename = original_filename
        self.stored_filename = stored_filename
        self.display_name = display_name
        self.file_size = file_size
        self.mime_type = mime_type
    
    def get_file_path(self):
        """Get the full file path for this asset"""
        from flask import current_app
        return os.path.join(
            current_app.config['UPLOAD_FOLDER'], 
            'users', 
            str(self.user_id), 
            f"{self.asset_type}s",
            self.stored_filename
        )
    
    def get_url(self):
        """Get the URL to access this asset"""
        return f"/static/assets/users/{self.user_id}/{self.asset_type}s/{self.stored_filename}"
    
    def get_file_size_mb(self):
        """Get file size in MB formatted"""
        return round(self.file_size / (1024 * 1024), 2)
    
    @classmethod
    def get_user_assets(cls, user_id, asset_type=None):
        """Get all assets for a user, optionally filtered by type"""
        query = cls.query.filter_by(user_id=user_id)
        if asset_type:
            query = query.filter_by(asset_type=asset_type)
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def create_asset(cls, user_id, asset_type, original_filename, file_content, mime_type):
        """Create a new user asset with file storage"""
        from flask import current_app
        import uuid
        
        # Generate unique filename
        file_extension = os.path.splitext(original_filename)[1]
        stored_filename = f"{uuid.uuid4().hex}{file_extension}"
        
        # Create display name from original filename
        display_name = os.path.splitext(original_filename)[0]
        
        # Create user directory if it doesn't exist
        user_dir = os.path.join(
            current_app.config['UPLOAD_FOLDER'], 
            'users', 
            str(user_id), 
            f"{asset_type}s"
        )
        os.makedirs(user_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(user_dir, stored_filename)
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Get file size
        file_size = len(file_content)
        
        # Create database record
        asset = cls(
            user_id=user_id,
            asset_type=asset_type,
            original_filename=original_filename,
            stored_filename=stored_filename,
            display_name=display_name,
            file_size=file_size,
            mime_type=mime_type
        )
        
        db.session.add(asset)
        db.session.commit()
        
        return asset
    
    def delete_asset(self):
        """Delete the asset file and database record"""
        try:
            # Delete file
            file_path = self.get_file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Delete database record
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False
    
    def to_dict(self):
        """Convert to dictionary for JSON responses"""
        return {
            'id': self.id,
            'asset_type': self.asset_type,
            'display_name': self.display_name,
            'file_size': self.get_file_size_mb(),
            'mime_type': self.mime_type,
            'url': self.get_url(),
            'created_at': self.created_at.isoformat(),
            'is_default': False
        }