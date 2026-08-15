from pydantic import BaseModel, Field
import os
from openai import OpenAI
import base64
import time
from pathlib import Path


class BaseImage(BaseModel):
    str_image: str = Field(..., description="Base64 encoded image string in the format 'data:image/png;base64,...' or a URL to the image")
    str_imageName: str = Field(..., description="Name of the image file a unique name identifier")
    str_imageDescriptionHuman: str = Field(..., description="Description of the image for human understanding")

class CollectedImages(BaseModel):
    obj_primaryImage: BaseImage = Field(..., description="Primary image object that will be used for the image generation")
    list_referenceImages: list[BaseImage] = Field(..., description="List of reference image objects that will be used for the image generation")
    str_userPrompt: str = Field(..., description="User prompt that will be used for the image generation")
    str_sceneDescription: str = Field(..., description="Detailed scene description that will be used for the image generation")

class ImageGenerationResponse(BaseModel):
    str_generatedImage:str = Field(..., description="Base64 encoded image string of the generated image")

    def save(self, param_str_filePath:str) -> None:
        with open(param_str_filePath, "wb") as f:
            # Remove the data URL prefix if present
            if self.str_generatedImage.startswith("data:image/png;base64,"):
                b64_data = self.str_generatedImage.split(",")[1]
            else:
                b64_data = self.str_generatedImage

            f.write(base64.b64decode(b64_data))   
class ImageGeneratorService:


    def __init__(self):

        self._obj_collectionImages: CollectedImages = None
        self._str_currentSceneDescription: str | None = None


    def add_primary_image(self, param_obj_primaryImage: BaseImage) -> None:
        """
        Add the primary image to the service.

        Args:
            param_obj_primaryImage (BaseImage): The primary image object to be added.
        """
        if self._obj_collectionImages is None:
            self._obj_collectionImages = CollectedImages(obj_primaryImage=param_obj_primaryImage, list_referenceImages=[], str_userPrompt="", str_sceneDescription="")
        else:
            self._obj_collectionImages.obj_primaryImage = param_obj_primaryImage
    
    def add_reference_image(self, param_obj_referenceImage:BaseImage) -> None:
        """
        Add a reference image to the service.

        Args:
            param_obj_referenceImage (BaseImage): The reference image object to be added.
        """
        if self._obj_collectionImages is None:
            self._obj_collectionImages = CollectedImages(obj_primaryImage=None, list_referenceImages=[param_obj_referenceImage], str_userPrompt="", str_sceneDescription="")
        else:
            self._obj_collectionImages.list_referenceImages.append(param_obj_referenceImage)

    def generate_detailed_task(self, param_str_userPrompt:str) -> None:
        """
        Generate a detailed task description based on the user prompt.

        Args:
            param_str_userPrompt (str): The user prompt to generate the detailed task description.
        """
        if self._obj_collectionImages is None:
            raise ValueError("No images have been added to the service.")
        

        self._obj_collectionImages.str_userPrompt = param_str_userPrompt

        # Minimal: build messages and ask the LLM for a scene description.
        # Use SceneDescriptionGenerator (keeps the call surface simple).
        generator = SceneDescriptionGenerator(style_injection=os.getenv("STYLE_INJECTION", ""))
        scene_text = generator.generate(self._obj_collectionImages)
        # store result on both the collection and a simple attribute
        self._obj_collectionImages.str_sceneDescription = scene_text
        self._str_currentSceneDescription = scene_text

        return scene_text

    def modify_scene_description(self, param_str_newSceneDescription:str) -> None:
        """
        Modify the existing scene description with a new one.

        Args:
            param_str_newSceneDescription (str): The new scene description to replace the existing one.
        """
        if self._obj_collectionImages is None:
            raise ValueError("No images have been added to the service.")
        
        self._obj_collectionImages.str_sceneDescription = param_str_newSceneDescription
        self._str_currentSceneDescription = param_str_newSceneDescription
    
    def generate_image(self) -> ImageGenerationResponse:
        """
        Generate an image based on the collected images and detailed task description.

        Returns:
            ImageGenerationResponse: The response containing the generated image.
        """
        if self._obj_collectionImages is None:
            raise ValueError("No images have been added to the service.")
        
        if not self._obj_collectionImages.str_sceneDescription:
            raise ValueError("Scene description has not been generated.")

        # Here you would implement the logic to generate an image based on the collected images and detailed task description.
        # Now, this whole collection of images, along with the individual image descriptions and the detailed task description, should be sent to the image genration model.
    

class ImageGenerator:
    def __init__(self, model: str | None = None, size: str | None = None) -> None:
        """Small wrapper around an image-generation API.

        The implementation keeps behavior minimal and mirrors the
        `SceneDescriptionGenerator` style: configuration via env or
        constructor and propagation of errors to the caller.
        """
        self._model = model or os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
        self._size = size or os.getenv("OPENAI_IMAGE_SIZE", "1024x1024")

    def _client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)

    def generate(self, param_obj_collection: CollectedImages) -> ImageGenerationResponse:
        """Generate an image from a `CollectedImages` object.

        This mirrors `SceneDescriptionGenerator.generate()` by building
        a `responses`-style message list that embeds the primary and
        reference images (as image messages) and then appends the
        `str_sceneDescription` followed by a final instruction asking
        the model to produce an image output (data URL / base64).
        """
        if param_obj_collection is None:
            raise ValueError("No image collection provided")

        if not param_obj_collection.str_sceneDescription:
            raise ValueError("Scene description is required for image generation")

        client = self._client()
        if client is None:
            raise RuntimeError("OpenAI API key not configured")

        list_messages = []

        # (Optional) small system instruction to prefer image outputs
        list_messages.append({"role": "system", "content": "You are an image generation assistant. Produce the final output as a data URL starting with 'data:image/png;base64,'."})

        # Add primary image as a user message
        if param_obj_collection.obj_primaryImage is not None:
            list_messages.append({"role": "user", "content": self._add_image_as_message(param_obj_collection.obj_primaryImage)})

        # Add all reference images
        for reference_image in param_obj_collection.list_referenceImages:
            list_messages.append({"role": "user", "content": self._add_image_as_message(reference_image)})

        # Append the detailed scene description (instead of the short user prompt)
        list_messages.append({"role": "user", "content": param_obj_collection.str_sceneDescription})

        # Final instruction: ask the model to generate the image (not text)
        list_messages.append({"role": "user", "content": "Generate the image now and return ONLY a single data URL (data:image/png;base64,<...>) representing the generated image. Do not include any extra text."})

        try:
            local_resp = client.responses.create(model=self._model, input=list_messages)

            # save the image response

            local_str_imageData = [output.result for output in local_resp.output if output.type == "image_generation_call"]
            local_str_imageData = local_str_imageData[0] if local_str_imageData else None

            return ImageGenerationResponse(str_generatedImage=local_str_imageData)

        except Exception:
            raise

    def _add_image_as_message(self, param_obj_image: BaseImage) -> list:
        local_list_contentMessage = []
        local_str_imageNameAndDescription = f"Image Name: {param_obj_image.str_imageName}\nDescription: {param_obj_image.str_imageDescriptionHuman}"
        local_list_contentMessage.append({"type": "input_text", "text": local_str_imageNameAndDescription})
        local_list_contentMessage.append({"type": "input_image", "image_url": param_obj_image.str_image})
        return local_list_contentMessage

class SceneDescriptionGenerator:

    def __init__(self, model: str | None = None, style_injection: str | None = None) -> None:
        """Small wrapper around an LLM call to produce and modify scene descriptions.

        Behavior is intentionally minimal: configuration via env or constructor
        and errors are propagated to the caller so the caller can handle them.
        """
        self._model = model or os.getenv("OPENAI_SCENE_DESCRIPTION_MODEL", "gpt-4.1-mini")
        self._style_injection = style_injection or ""
        self._str_currentSceneDescription: str | None = None

    def _client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)

    def generate(self, collection: CollectedImages) -> str:
        """Generate a detailed scene description from a `CollectedImages` object.

        The generator embeds base and reference images (as data URLs) plus any
        human descriptions and the user's short prompt into a single LLM call.
        Exceptions from the underlying client bubble up to the caller.
        """

        client = self._client()
        if client is None:
            raise RuntimeError("OpenAI API key not configured")

        list_messages = []

        # Add the style injection as a system message 
        list_messages.append({"role": "system", "content": self._style_injection})

        # Add the base image and it's description as a user message
        list_messages.append({"role": "user", "content": self._add_image_as_message(collection.obj_primaryImage)})

        # add all the reference images and their descriptions as user messages

        for reference_image in collection.list_referenceImages:
            list_messages.append({"role": "user", "content": self._add_image_as_message(reference_image)})

        # Finally, add the user's short prompt as a user message
        list_messages.append({"role": "user", "content": collection.str_userPrompt})


        # use the responses api from openai to get the scene description

        local_obj_response = client.responses.create(
            model=self._model,
            input=list_messages,
        )

        self._str_currentSceneDescription = local_obj_response.output_text

        return local_obj_response.output_text

    
    def _add_image_as_message(self, param_obj_image: BaseImage)-> list:

        local_list_contentMessage = []
        local_str_imageNameAndDescription = f"Image Name: {param_obj_image.str_imageName}\nDescription: {param_obj_image.str_imageDescriptionHuman}"
        local_list_contentMessage.append({"type" : "input_text", "text": local_str_imageNameAndDescription})
        local_list_contentMessage.append({"type" : "input_image", "image_url": param_obj_image.str_image})


        return local_list_contentMessage