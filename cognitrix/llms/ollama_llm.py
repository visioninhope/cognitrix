from cognitrix.llms.base import LLM, LLMResponse
from cognitrix.utils import image_to_base64
from typing import Any, Optional
from dotenv import load_dotenv
from ollama import Client
import logging
import sys
import os

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%d-%b-%y %H:%M:%S',
    level=logging.WARNING
)
logger = logging.getLogger('cognitrix.log')
load_dotenv()


class Ollama(LLM):
    """A class for interacting with the Ollama API.

    Args:
        model (str): The name of the Local model to use
        temperature (float): The temperature to use when generating text
        base_url (str): Base url of local llm server
        chat_history (list): Chat history
        max_tokens (int): The maximum number of tokens to generate in the completion
        supports_system_prompt (bool): Flag to indicate if system prompt should be supported
        system_prompt (str): System prompt to prepend to queries
    """
    
    model: str = 'llama3'
    """model endpoint to use""" 
    
    vision_model: str = 'llava-phi3'
    """vision model endpoint to use""" 
    
    temperature: float = 0.1
    """What sampling temperature to use.""" 
    
    api_key: str = 'not-needed'
    """API key""" 
    
    base_url: str = 'http://localhost:11434'
    """Base url of local llm server"""
    
    max_tokens: int = 4048
    """The maximum number of tokens to generate in the completion.""" 
    
    chat_history: list[str] = []
    """Chat history"""
    
    supports_system_prompt: bool = True
    """Flag to indicate if system prompt should be supported"""
    
    system_prompt: str = ""
    """System prompt to prepend to queries"""
    
    def format_query(self, message: dict[str, str]) -> list:
        """Formats a message for the Claude API.

        Args:
            message (dict[str, str]): The message to be formatted for the Claude API.

        Returns:
            list: A list of formatted messages for the Claude API.
        """
        
        formatted_message = [*self.chat_history, message]
        
        messages = []
        
        for fm in formatted_message:
            if fm['type'] == 'text':
                messages.append({
                    "role": fm['role'].lower(),
                    "content": fm['message']
                })
            else:
                base64_image = image_to_base64(fm['image'])
                self.model = self.vision_model
                new_message = {
                    "role": fm['role'].lower(),
                    "content": "This is the result of the latest screenshot",
                    "images": [base64_image]
                }
                messages.append(new_message)
            
        return messages

    def __call__(self, query: dict, **kwds: dict):
        """Generates a response to a query using the OpenAI API.

        Args:
            query (dict): The query to generate a response to.
            kwds (dict): Additional keyword arguments to pass to the OpenAI API.

        Returns:
            A string containing the generated response.
        """
        
        if not self.client:
            self.client = Client('http://localhost:11434')
        
        formatted_messages = self.format_query(query)
        
        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "user", "content": self.system_prompt},
                *formatted_messages
            ],
            stream=False,
        )
        
        return LLMResponse(response['message']['content'])                        #type: ignore
