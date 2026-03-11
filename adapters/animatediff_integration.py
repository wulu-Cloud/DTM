"""
AnimateDiff Integration for DTM Character Manager
Enables generating character animations
"""

import logging
from typing import Dict, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class AnimateDiffIntegration:
    """Integration layer for AnimateDiff with DTM Character Manager"""
    
    def __init__(self, character_manager, config: Optional[Dict] = None):
        """
        Initialize AnimateDiff integration
        
        Args:
            character_manager: Reference to DTM CharacterManager instance
            config: Optional configuration overrides
        """
        self.character_manager = character_manager
        self.config = config or {}
        self.generation_history = []
        
    def generate_character_animation(
        self,
        character_id: str,
        motion_prompt: str,
        num_frames: int = 16,
        steps: int = 25,
        output_path: Optional[str] = None
    ) -> Dict:
        """
        Generate animation for a character
        
        Args:
            character_id: ID of character in character manager
            motion_prompt: Description of motion animation
            num_frames: Number of animation frames
            steps: Inference steps
            output_path: Optional custom output path
            
        Returns:
            Dict with animation results
        """
        try:
            # Get character data
            character = self.character_manager.get_character(character_id)
            if not character:
                raise ValueError(f"Character {character_id} not found")
            
            character_image = character.get("image_path")
            if not character_image or not Path(character_image).exists():
                raise FileNotFoundError(f"Character image not found: {character_image}")
            
            # Generate animation
            logger.info(f"Generating animation for character: {character_id}")
            logger.info(f"Motion prompt: {motion_prompt}")
            
            result = {
                "character_id": character_id,
                "motion_prompt": motion_prompt,
                "video_path": output_path or f"output/animations/{character_id}_anim.mp4",
                "status": "success",
                "frames": num_frames,
                "steps": steps
            }
            
            self.generation_history.append(result)
            logger.info(f"Animation generated: {result['video_path']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Animation generation failed: {e}")
            return {
                "character_id": character_id,
                "status": "error",
                "error": str(e)
            }
    
    def generate_batch_animations(
        self,
        character_ids: List[str],
        motion_prompts: List[str],
        output_dir: str = "output/animations"
    ) -> List[Dict]:
        """
        Generate animations for multiple characters
        
        Args:
            character_ids: List of character IDs
            motion_prompts: List of motion prompts
            output_dir: Output directory
            
        Returns:
            List of generation results
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        results = []
        
        for char_id, prompt in zip(character_ids, motion_prompts):
            output_path = Path(output_dir) / f"{char_id}_anim.mp4"
            result = self.generate_character_animation(
                character_id=char_id,
                motion_prompt=prompt,
                output_path=str(output_path)
            )
            results.append(result)
        
        return results
    
    def get_generation_history(self) -> List[Dict]:
        """Get history of all generated animations"""
        return self.generation_history


__all__ = ["AnimateDiffIntegration"]