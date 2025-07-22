from app.extensions import db
from datetime import datetime
from decimal import Decimal

class AlertConfiguration(db.Model):
    __tablename__ = 'alert_configurations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tab_number = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Alert Message Settings
    text_template = db.Column(db.Text, default='{name}-ээс **[{amount}₮]** donation орж ирлээ!')
    minimum_amount = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    
    # Animation Settings
    visible_time = db.Column(db.Integer, default=5000)  # milliseconds
    animation_speed = db.Column(db.Integer, default=1000)  # milliseconds
    transition_type = db.Column(db.String(50), default='fade-in')
    
    # Image Settings
    image_position = db.Column(db.String(20), default='left')
    image_size = db.Column(db.Integer, default=100)
    selected_gif_id = db.Column(db.Integer, db.ForeignKey('user_assets.id'))
    default_gif_name = db.Column(db.String(100), default='party.gif')
    
    # Sound Settings
    sound_volume = db.Column(db.Integer, default=50)
    selected_sound_id = db.Column(db.Integer, db.ForeignKey('user_assets.id'))
    default_sound_name = db.Column(db.String(100), default='twitch-donation.mp3')
    
    # TTS Settings
    tts_enabled = db.Column(db.Boolean, default=False)
    tts_minimum_amount = db.Column(db.Numeric(10, 2), default=Decimal('1000.00'))
    tts_speed = db.Column(db.Float, default=1.0)
    tts_voice = db.Column(db.String(50), default='FEMALE1')
    tts_pitch = db.Column(db.Float, default=1.0)
    
    # Donator Settings
    donator_image_size = db.Column(db.Integer, default=50)
    donator_name_size = db.Column(db.Integer, default=24)
    donator_name_weight = db.Column(db.String(20), default='bold')
    donator_alignment = db.Column(db.String(20), default='center')
    donator_color = db.Column(db.String(7), default='#ffffff')
    
    # Text Template Style Settings
    template_size = db.Column(db.Integer, default=20)
    template_weight = db.Column(db.String(20), default='bold')
    template_alignment = db.Column(db.String(20), default='center')
    template_base_color = db.Column(db.String(7), default='#ffffff')
    template_accent_color = db.Column(db.String(7), default='#ffd700')
    
    # Message Style Settings
    message_size = db.Column(db.Integer, default=16)
    message_weight = db.Column(db.String(20), default='normal')
    message_style = db.Column(db.String(20), default='normal')
    message_alignment = db.Column(db.String(20), default='center')
    message_color = db.Column(db.String(7), default='#ffffff')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='alert_configurations')
    selected_gif = db.relationship('UserAsset', foreign_keys=[selected_gif_id], backref='gif_alert_configs')
    selected_sound = db.relationship('UserAsset', foreign_keys=[selected_sound_id], backref='sound_alert_configs')
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('user_id', 'tab_number', name='unique_user_tab'),
        db.Index('idx_user_tab', 'user_id', 'tab_number'),
        db.Index('idx_user_active', 'user_id', 'is_active'),
    )
    
    def __repr__(self):
        return f'<AlertConfiguration {self.user_id}-{self.tab_number}>'
    
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
    
    def to_dict(self):
        """Convert alert configuration to dictionary for frontend"""
        return {
            'id': self.id,
            'tab_number': self.tab_number,
            'is_active': self.is_active,
            'text_template': self.text_template,
            'minimum_amount': float(self.minimum_amount) if self.minimum_amount else 0.0,
            'visible_time': self.visible_time,
            'animation_speed': self.animation_speed,
            'transition_type': self.transition_type,
            'image_position': self.image_position,
            'image_size': self.image_size,
            'selected_gif_id': self.selected_gif_id,
            'default_gif_name': self.default_gif_name,
            'gif_url': self.get_gif_url(),
            'sound_volume': self.sound_volume,
            'selected_sound_id': self.selected_sound_id,
            'default_sound_name': self.default_sound_name,
            'sound_url': self.get_sound_url(),
            'tts_enabled': self.tts_enabled,
            'tts_minimum_amount': float(self.tts_minimum_amount) if self.tts_minimum_amount else 0.0,
            'tts_speed': self.tts_speed,
            'tts_voice': self.tts_voice,
            'tts_pitch': self.tts_pitch,
            'donator_image_size': self.donator_image_size,
            'donator_name_size': self.donator_name_size,
            'donator_name_weight': self.donator_name_weight,
            'donator_alignment': self.donator_alignment,
            'donator_color': self.donator_color,
            'template_size': self.template_size,
            'template_weight': self.template_weight,
            'template_alignment': self.template_alignment,
            'template_base_color': self.template_base_color,
            'template_accent_color': self.template_accent_color,
            'message_size': self.message_size,
            'message_weight': self.message_weight,
            'message_style': self.message_style,
            'message_alignment': self.message_alignment,
            'message_color': self.message_color,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_default_config(cls, user_id, tab_number=1):
        """Create a default alert configuration for a user"""
        return cls(
            user_id=user_id,
            tab_number=tab_number,
            # All other fields will use their defaults
        )
    
    @classmethod
    def get_user_configs(cls, user_id, active_only=True):
        """Get all alert configurations for a user"""
        query = cls.query.filter_by(user_id=user_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(cls.tab_number).all()
    
    @classmethod
    def get_config_for_amount(cls, user_id, amount):
        """Get the appropriate alert configuration for a donation amount"""
        configs = cls.query.filter_by(
            user_id=user_id, 
            is_active=True
        ).filter(
            cls.minimum_amount <= amount
        ).order_by(cls.minimum_amount.desc()).first()
        
        return configs
    
    @classmethod
    def find_next_available_amount(cls, user_id, base_amount, exclude_tab_number=None):
        """Find the next available minimum amount for a user"""
        from decimal import Decimal
        
        # Get all existing amounts for this user
        query = cls.query.filter_by(user_id=user_id, is_active=True)
        if exclude_tab_number:
            query = query.filter(cls.tab_number != exclude_tab_number)
        
        existing_amounts = [float(config.minimum_amount) for config in query.all()]
        existing_amounts.sort()
        
        base_amount = float(base_amount)
        
        # If base amount is 0, suggest increments of 500
        if base_amount == 0:
            suggestion = 500
            while suggestion in existing_amounts:
                suggestion += 500
            return Decimal(str(suggestion))
        
        # For other amounts, try increments
        suggestion = base_amount
        increment = 500 if base_amount >= 1000 else 100
        
        while suggestion in existing_amounts:
            suggestion += increment
        
        return Decimal(str(suggestion))
    
    def update_from_dict(self, data):
        """Update configuration from dictionary data"""
        for key, value in data.items():
            if hasattr(self, key):
                # Convert string decimals to Decimal objects
                if key in ['minimum_amount', 'tts_minimum_amount'] and value is not None:
                    value = Decimal(str(value))
                setattr(self, key, value)
        
        self.updated_at = datetime.utcnow()
    
    def duplicate_to_tab(self, new_tab_number):
        """Duplicate this configuration to a new tab number"""
        new_config = AlertConfiguration()
        
        # Copy all settings except id, user_id, tab_number, timestamps
        exclude_fields = {'id', 'user_id', 'tab_number', 'created_at', 'updated_at'}
        
        for column in self.__table__.columns:
            if column.name not in exclude_fields:
                setattr(new_config, column.name, getattr(self, column.name))
        
        new_config.user_id = self.user_id
        new_config.tab_number = new_tab_number
        new_config.created_at = datetime.utcnow()
        new_config.updated_at = datetime.utcnow()
        
        return new_config