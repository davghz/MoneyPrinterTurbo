"""
This module defines the abstract base class for Text-to-Speech (TTS) services.

It provides an interface that all concrete TTS service implementations should adhere to,
ensuring a consistent way to synthesize speech and retrieve available voices across different providers.
"""
from abc import ABC, abstractmethod
from typing import Any, List, Tuple

class TextToSpeechService(ABC):
    """
    Abstract Base Class (ABC) for Text-to-Speech services.

    This class defines the contract for TTS services. Implementations of this interface
    should provide concrete methods for speech synthesis and voice retrieval.
    The primary goal is to offer a unified way to interact with various TTS engines.
    """

    @abstractmethod
    def synthesize_speech(
        self, text: str, voice_id: str, output_filename: str, **kwargs
    ) -> Tuple[str, Any]:
        """
        Synthesizes speech from the provided text and saves it to an audio file.

        Implementations should handle API calls to the specific TTS provider,
        manage audio data, and save it to the specified file. They should also
        return any subtitle-related information if available (e.g., word timings,
        SubMaker object).

        Args:
            text: The input string to be synthesized into speech.
            voice_id: The identifier for the voice to be used for synthesis.
                      The format of this ID may vary depending on the TTS provider.
            output_filename: The desired path (including filename and extension)
                             for the generated audio file.
            **kwargs: Additional provider-specific keyword arguments. This allows for
                      flexibility in passing parameters like speaking rate, pitch,
                      audio encoding, etc., to different TTS engines.

        Returns:
            A tuple where the first element is a string representing the path
            to the generated audio file, and the second element is subtitle-related
            data. The nature of subtitle data can vary (e.g., a list of timepoints,
            a SubMaker object, or None if not applicable).
        """
        pass

    @abstractmethod
    def get_available_voices(self, **kwargs) -> List[str]:
        """
        Retrieves a list of available voice IDs from the TTS service.

        Implementations should query the TTS provider (if possible) to get an
        up-to-date list of voices. The format of the voice IDs in the returned
        list should be consistent with what `synthesize_speech` expects for `voice_id`.

        Args:
            **kwargs: Additional provider-specific keyword arguments, e.g., for filtering
                      voices by language or other criteria.

        Returns:
            A list of strings, where each string is an available voice ID.
            Returns an empty list if voices cannot be retrieved or none are available.
        """
        pass
