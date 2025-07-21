from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from app.utils.chimege_tts import ChimegeTTS
from app.utils.tts_limiter import TTSLimiter
import os
import tempfile
import logging

tts_bp = Blueprint('tts', __name__)

@tts_bp.route('/api/tts/synthesize', methods=['POST'])
@login_required
def synthesize_tts():
    """Synthesize text to speech using Chimege TTS"""
    try:
        current_app.logger.info("TTS SYNTHESIZE: Request received")
        data = request.get_json()
        current_app.logger.info(f"TTS SYNTHESIZE: Data received: {data}")
        
        if not data or 'text' not in data:
            current_app.logger.error("TTS SYNTHESIZE: No text provided")
            return jsonify({'error': 'Text is required'}), 400
        
        text = data['text'].strip()
        voice = data.get('voice', 'FEMALE3v2')
        speed = float(data.get('speed', 1.0))
        pitch = float(data.get('pitch', 1.0))
        request_type = data.get('request_type', 'donation')
        
        current_app.logger.info(f"TTS SYNTHESIZE: User {current_user.id} requesting TTS")
        current_app.logger.info(f"TTS SYNTHESIZE: Text='{text}', Voice={voice}, Speed={speed}, Pitch={pitch}, Type={request_type}")
        
        # Initialize limiter
        limiter = TTSLimiter(current_user)
        current_app.logger.info("TTS SYNTHESIZE: Checking usage limits")
        
        # Check usage limits
        limit_check = limiter.check_limits(current_user.id, text, request_type)
        current_app.logger.info(f"TTS SYNTHESIZE: Limit check result: {limit_check}")
        
        if not limit_check['allowed']:
            current_app.logger.warning(f"TTS SYNTHESIZE: Usage limit exceeded for user {current_user.id}: {limit_check['reason']}")
            # Log failed attempt
            limiter.log_request(
                current_user.id, 
                text, 
                voice, 
                request_type, 
                success=False, 
                error_message=limit_check['reason']
            )
            return jsonify({
                'error': limit_check['reason'],
                'usage_info': limit_check['usage_info']
            }), 429  # Too Many Requests
        
        # Validate text length
        if len(text) < 2:
            return jsonify({'error': 'Text too short'}), 400
        if len(text) > 300:
            text = text[:300]
        
        # Initialize TTS client
        current_app.logger.info("TTS SYNTHESIZE: Initializing Chimege TTS client")
        tts = ChimegeTTS()
        
        # Normalize text for better pronunciation
        current_app.logger.info(f"TTS SYNTHESIZE: Normalizing text: '{text}'")
        normalized_text = tts.normalize_text(text)
        current_app.logger.info(f"TTS SYNTHESIZE: Normalized text: '{normalized_text}'")
        
        # Generate TTS audio
        current_app.logger.info("TTS SYNTHESIZE: Calling Chimege API for synthesis")
        audio_path = tts.synthesize_text(
            normalized_text, 
            voice_id=voice, 
            speed=speed, 
            pitch=pitch
        )
        
        if not audio_path:
            current_app.logger.error("TTS SYNTHESIZE: Audio synthesis failed")
            # Log failed synthesis
            limiter.log_request(
                current_user.id, 
                text, 
                voice, 
                request_type, 
                success=False, 
                error_message="TTS synthesis failed"
            )
            return jsonify({'error': 'TTS synthesis failed'}), 500
        
        current_app.logger.info(f"TTS SYNTHESIZE: Audio generated successfully: {audio_path}")
        
        # Log successful request
        limiter.log_request(current_user.id, text, voice, request_type, success=True)
        current_app.logger.info("TTS SYNTHESIZE: Request logged successfully")
        
        # Return audio file
        current_app.logger.info("TTS SYNTHESIZE: Returning audio file to client")
        return send_file(
            audio_path,
            mimetype='audio/wav',
            as_attachment=False,
            download_name='tts_audio.wav'
        )
        
    except Exception as e:
        current_app.logger.error(f"TTS SYNTHESIZE: Exception occurred: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@tts_bp.route('/api/tts/voices', methods=['GET'])
@login_required
def get_voices():
    """Get available TTS voices"""
    try:
        tts = ChimegeTTS()
        voices = tts.get_available_voices()
        return jsonify(voices)
    except Exception as e:
        logging.error(f"TTS voices error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@tts_bp.route('/api/tts/test', methods=['POST'])
@login_required
def test_tts():
    """Test TTS with sample text"""
    try:
        current_app.logger.info("TTS TEST: Test request received")
        data = request.get_json()
        current_app.logger.info(f"TTS TEST: Data received: {data}")
        
        voice = data.get('voice', 'FEMALE3v2')
        speed = float(data.get('speed', 1.0))
        pitch = float(data.get('pitch', 1.0))
        
        # Use sample text for testing (simulating a donation message)
        test_text = data.get('text', "Сайн байна уу? Энэ бол туршилтын мессеж юм!")
        
        current_app.logger.info(f"TTS TEST: User {current_user.id} testing TTS")
        current_app.logger.info(f"TTS TEST: Text='{test_text}', Voice={voice}, Speed={speed}, Pitch={pitch}")
        
        # Initialize limiter
        limiter = TTSLimiter(current_user)
        
        # Check usage limits for test requests
        limit_check = limiter.check_limits(current_user.id, test_text, 'test')
        if not limit_check['allowed']:
            # Log failed attempt
            limiter.log_request(
                current_user.id, 
                test_text, 
                voice, 
                'test', 
                success=False, 
                error_message=limit_check['reason']
            )
            return jsonify({
                'error': limit_check['reason'],
                'usage_info': limit_check['usage_info']
            }), 429  # Too Many Requests
        
        # Initialize TTS client
        tts = ChimegeTTS()
        
        # Generate TTS audio
        audio_path = tts.synthesize_text(
            test_text, 
            voice_id=voice, 
            speed=speed, 
            pitch=pitch
        )
        
        if not audio_path:
            # Log failed synthesis
            limiter.log_request(
                current_user.id, 
                test_text, 
                voice, 
                'test', 
                success=False, 
                error_message="TTS synthesis failed"
            )
            return jsonify({'error': 'TTS synthesis failed'}), 500
        
        # Log successful test request
        limiter.log_request(current_user.id, test_text, voice, 'test', success=True)
        
        # Return audio file
        return send_file(
            audio_path,
            mimetype='audio/wav',
            as_attachment=False,
            download_name='tts_test.wav'
        )
        
    except Exception as e:
        logging.error(f"TTS test error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@tts_bp.route('/api/tts/usage', methods=['GET'])
@login_required
def get_usage():
    """Get user's TTS usage statistics"""
    try:
        limiter = TTSLimiter(current_user)
        usage_summary = limiter.get_usage_summary(current_user.id)
        return jsonify(usage_summary)
    except Exception as e:
        logging.error(f"TTS usage error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@tts_bp.route('/api/tts/cleanup', methods=['POST'])
def cleanup_tts_file():
    """Clean up TTS audio file after playback"""
    try:
        data = request.get_json()
        file_url = data.get('file_url')
        
        if not file_url or not file_url.startswith('/static/uploads/tts/'):
            return jsonify({
                'success': False,
                'error': 'Invalid file URL'
            }), 400
        
        # Extract filename from URL
        filename = file_url.split('/')[-1]
        
        # Build full file path
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
        file_path = os.path.join(upload_folder, 'tts', filename)
        
        # Delete the file
        if os.path.exists(file_path):
            os.remove(file_path)
            current_app.logger.info(f"TTS CLEANUP: Deleted file: {file_path}")
            
            return jsonify({
                'success': True,
                'message': f'File {filename} deleted successfully'
            })
        else:
            current_app.logger.warning(f"TTS CLEANUP: File not found: {file_path}")
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
            
    except Exception as e:
        current_app.logger.error(f"TTS CLEANUP: Error deleting file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500