from pydantic import BaseModel, Field


class BaseImage(BaseModel):
    str_image: str = Field(..., description="Base64 encoded image string")
    str_imageName: str = Field(..., description="Name of the image file a unique name identifier")
    str_imageDescriptionHuman: str = Field(..., description="Description of the image for human understanding")

class CollectedImages(BaseModel):
    obj_primaryImage: BaseImage = Field(..., description="Primary image object that will be used for the image generation")
    list_referenceImages: list[BaseImage] = Field(..., description="List of reference image objects that will be used for the image generation")
    str_userPrompt: str = Field(..., description="User prompt that will be used for the image generation")
    str_sceneDescription: str = Field(..., description="Detailed scene description that will be used for the image generation")

class ImageGenerationResponse(BaseModel):
    str_generatedImage:str = Field(..., description="Base64 encoded image string of the generated image")

class ImageGeneratorService:


    def __init__(self):

        self._obj_collectionImages: CollectedImages = None


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

        # Here you would implement the logic to generate a detailed scene description based on the user prompt.

        # we need to send the primary image and reference images to the gpt-4 model and ask to generate the detailed scene description needed for an image generation model. 
        # Then it should be reviewed by the user and if the user approves it, then we need to store the detailed scene description in the service.
    
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

    def __init__(self):
        ...

    def generate(self)-> ImageGenerationResponse:
        """
        Creates the image generation by sending the collected images and detailed task description to the image generation model.

        Returns:
            ImageGenerationResponse: The response containing the generated image.
        """
        return ImageGenerationResponse()

class SceneDescriptionGenerator:

    def __init__(self):
        ...

    def generate(self, param_str_userPrompt:str) -> str:
        """
        Generates a detailed scene description based on the user prompt.

        Args:
            param_str_userPrompt (str): The user prompt to generate the detailed scene description.

        Returns:
            str: The generated detailed scene description.
        """
        return "Detailed scene description based on the user prompt."

    def get_scene_description(self, param_str_userPrompt:str) -> str:
        """
        Gets the detailed scene description based on the user prompt.

        Args:
            param_str_userPrompt (str): The user prompt to get the detailed scene description.

        Returns:
            str: The detailed scene description based on the user prompt.
        """
        return "Detailed scene description based on the user prompt."

    def apply_modification(self, param_str_modification:str) -> str:
        """
        Applies modifications to the detailed scene description based on user feedback.

        Args:
            param_str_modification (str): The modification to apply to the detailed scene description based on user feedback.

        Returns:
            str: The modified detailed scene description based on user feedback.
        """
        return "Modified detailed scene description based on user feedback."

    def get_final_scene_description(self, param_str_modifiedSceneDescription:str) -> str:
        """
        Gets the final detailed scene description after user approval.

        Args:
            param_str_modifiedSceneDescription (str): The modified detailed scene description to finalize.

        Returns:
            str: The final detailed scene description after user approval.
        """
        return "Final detailed scene description after user approval."