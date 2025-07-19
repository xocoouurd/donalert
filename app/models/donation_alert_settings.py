from app.extensions import db
from datetime import datetime
import json

class DonationAlertSettings(db.Model):
    __tablename__ = 'donation_alert_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Text Template Settings
    text_template = db.Column(db.Text, default="{name}-ээс **[{amount}₮]** donation орж ирлээ!")
    minimum_amount = db.Column(db.Integer, default=0)  # 0 = no minimum
    
    # Animation Settings
    visible_time = db.Column(db.Integer, default=5000)  # milliseconds
    animation_speed = db.Column(db.Integer, default=1000)  # milliseconds
    transition_type = db.Column(db.String(50), default="fade-in")  # fade-in, slide-up, etc.
    
    # Text to Speech Settings
    tts_enabled = db.Column(db.Boolean, default=False)
    tts_minimum_amount = db.Column(db.Integer, default=1000)
    tts_voice = db.Column(db.String(50), default="FEMALE3v2")
    tts_speed = db.Column(db.Float, default=1.0)
    tts_pitch = db.Column(db.Float, default=1.0)
    
    # Donation Image Settings
    image_position = db.Column(db.String(20), default="top")  # top, left, right, bottom
    selected_gif_id = db.Column(db.Integer, db.ForeignKey('user_assets.id'), nullable=True)
    default_gif_name = db.Column(db.String(100), default="party.gif")  # fallback to default
    image_size = db.Column(db.Integer, default=100)  # percentage, 50-200%
    
    # Sound Settings
    selected_sound_id = db.Column(db.Integer, db.ForeignKey('user_assets.id'), nullable=True)
    default_sound_name = db.Column(db.String(100), default="twitch-doanation.mp3")  # fallback to default
    sound_volume = db.Column(db.Integer, default=50)  # 0-100%
    
    # Donator Settings
    donator_image_size = db.Column(db.Integer, default=50)  # pixels
    donator_name_size = db.Column(db.Integer, default=24)  # pixels
    donator_name_weight = db.Column(db.String(20), default="bold")  # normal, bold
    donator_alignment = db.Column(db.String(20), default="center")  # left, center, right
    donator_color = db.Column(db.String(7), default="#FFFFFF")  # hex color
    
    # Text Template Style Settings
    template_size = db.Column(db.Integer, default=18)  # pixels
    template_weight = db.Column(db.String(20), default="normal")  # normal, bold
    template_alignment = db.Column(db.String(20), default="left")  # left, center, right
    template_accent_color = db.Column(db.String(7), default="#6366F1")  # hex color for [text]
    template_base_color = db.Column(db.String(7), default="#FFFFFF")  # hex color for normal text
    
    # Message Style Settings
    message_size = db.Column(db.Integer, default=16)  # pixels
    message_weight = db.Column(db.String(20), default="normal")  # normal, bold
    message_alignment = db.Column(db.String(20), default="left")  # left, center, right
    message_style = db.Column(db.String(20), default="normal")  # normal, italic, oblique
    message_color = db.Column(db.String(7), default="#E5E7EB")  # hex color
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('donation_alert_settings', uselist=False, cascade='all, delete-orphan'))
    selected_gif = db.relationship('UserAsset', foreign_keys=[selected_gif_id], post_update=True)
    selected_sound = db.relationship('UserAsset', foreign_keys=[selected_sound_id], post_update=True)
    
    def __init__(self, user_id, **kwargs):
        self.user_id = user_id
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    def get_or_create_for_user(cls, user_id):
        """Get existing settings or create default ones for user"""
        settings = cls.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = cls(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def get_gif_url(self):
        """Get the URL for the selected gif (user or default)"""
        if self.selected_gif:
            return self.selected_gif.get_url()
        else:
            return f"/static/assets/default/gifs/{self.default_gif_name}"
    
    def get_sound_url(self):
        """Get the URL for the selected sound (user or default)"""
        if self.selected_sound:
            return self.selected_sound.get_url()
        else:
            return f"/static/assets/default/sounds/{self.default_sound_name}"
    
    def update_settings(self, **kwargs):
        """Update settings with new values"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convert settings to dictionary for JSON responses"""
        return {
            'text_template': self.text_template,
            'minimum_amount': self.minimum_amount,
            'visible_time': self.visible_time,
            'animation_speed': self.animation_speed,
            'transition_type': self.transition_type,
            'tts_enabled': self.tts_enabled,
            'tts_minimum_amount': self.tts_minimum_amount,
            'tts_voice': self.tts_voice,
            'tts_speed': self.tts_speed,
            'tts_pitch': self.tts_pitch,
            'image_position': self.image_position,
            'selected_gif_id': self.selected_gif_id,
            'default_gif_name': self.default_gif_name,
            'image_size': self.image_size,
            'selected_sound_id': self.selected_sound_id,
            'default_sound_name': self.default_sound_name,
            'sound_volume': self.sound_volume,
            'donator_image_size': self.donator_image_size,
            'donator_name_size': self.donator_name_size,
            'donator_name_weight': self.donator_name_weight,
            'donator_alignment': self.donator_alignment,
            'donator_color': self.donator_color,
            'template_size': self.template_size,
            'template_weight': self.template_weight,
            'template_alignment': self.template_alignment,
            'template_accent_color': self.template_accent_color,
            'template_base_color': self.template_base_color,
            'message_size': self.message_size,
            'message_weight': self.message_weight,
            'message_alignment': self.message_alignment,
            'message_style': self.message_style,
            'message_color': self.message_color,
            'gif_url': self.get_gif_url(),
            'sound_url': self.get_sound_url()
        }