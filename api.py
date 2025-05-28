import os
import json
import requests
from typing import Dict, Any

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

def analyze_sandbox_environment(system_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze system information using OpenRouter.ai to detect if the environment is a sandbox.
    
    Args:
        system_info: Dictionary containing system information from send_permission_card
        
    Returns:
        Dictionary containing analysis results and confidence score
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set")

    analysis_prompt = f"""
    Analyze the following system information to determine if it's running in a sandbox environment.
    Consider these factors:
    1. Hardware characteristics (CPU cores, RAM)
    2. System uptime
    3. Process information
    4. Path information
    5. Username and hostname patterns
    6. IP address characteristics
    7. Temporary file count
    8. GPU information (GPU Name, GPU Memory)
    
    Please provide your analysis in the following exact format:
    
    System Information:
    - CPU Cores: {system_info.get('core_num')}
    - RAM: {system_info.get('ram')} GB
    - Resolution: {system_info.get('resolution')}
    - Current Path: {system_info.get('current_path')}
    - Parent Process: {system_info.get('parent_process')}
    - Boot Time: {system_info.get('boot_time')} minutes
    - Username: {system_info.get('username')}
    - Hostname: {system_info.get('hostname')}
    - External IP: {system_info.get('external_ip')}
    - Temporary File Count: {system_info.get('tempfile_num')}
    - GPU Name: {system_info.get('GPU_name')}
    - GPU Memory: {system_info.get('GPU_memory')} MB

    Please provide your analysis in the following exact format:

    Is this likely a sandbox? [Yes/No]
    Confidence score: [0-100]
    
    Key indicators:
    [List the key indicators that led to this conclusion, with special focus on GPU characteristics]
    
    Recommendations:
    [List recommendations for additional checks]
    
    Note: 
    1. Please strictly follow this format
    2. The confidence score should be a number between 0 and 100
    3. If GPU name contains 'VMware', 'VirtualBox', 'QEMU', or similar, and GPU memory is very low (e.g., 4MB), this is a strong indicator of a VM environment
    4. Consider multiple factors together, but give high weight to GPU characteristics
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Sandbox Detection"  
    }

    data = {
        "model": "meta-llama/llama-3.3-8b-instruct:free",  
        "messages": [
            {
                "role": "system",
                "content": "You are an expert in system security and sandbox detection, with special expertise in identifying virtual machines and sandbox environments. Pay particular attention to GPU characteristics as they are often the most reliable indicators of a VM environment."
            },
            {
                "role": "user",
                "content": analysis_prompt
            }
        ],
        "temperature": 0.3  # Lower temperature for more consistent analysis
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        analysis = result['choices'][0]['message']['content']
        
        # Extract information with better error handling
        try:
            is_sandbox = "Yes" in analysis.split("Is this likely a sandbox?")[1].split("\n")[0]
        except IndexError:
            print("Warning: Could not parse sandbox status from response")
            is_sandbox = False
            
        try:
            confidence_text = analysis.split("Confidence score:")[1].split("\n")[0].strip()
            confidence_score = int(confidence_text)
        except (IndexError, ValueError) as e:
            print(f"Warning: Could not parse confidence score from response: {str(e)}")
            confidence_score = 0
        
        return {
            "is_sandbox": is_sandbox,
            "confidence_score": confidence_score,
            "analysis": analysis
        }
        
    except requests.exceptions.RequestException as e:
        print(f"\n=== API Request Error ===")
        print(f"Error: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        print("========================\n")
        raise Exception(f"Error calling OpenRouter API: {str(e)}")

def get_sandbox_analysis(index: int) -> Dict[str, Any]:
    """
    Get sandbox analysis for a specific system index.
    
    Args:
        index: The system index to analyze
        
    Returns:
        Dictionary containing sandbox analysis results
    """
    from tools import fetch_data_basic_info, fetch_data_env_info
    
    # Fetch system information
    basic_info_result = fetch_data_basic_info(index)
    env_info_result = fetch_data_env_info(index)
    
    # Check if we got valid data
    if not basic_info_result or not env_info_result:
        raise ValueError(f"Failed to fetch data for index {index}")
    
    basic_info = basic_info_result[0]
    env_info = env_info_result[0]
    
    # Check if all basic info fields have values
    if len(basic_info) < 5 or any(not value for value in basic_info[:5]):
        print(f"Warning: Incomplete basic info for index {index}")
        return {
            "is_sandbox": False,
            "confidence_score": 0,
            "analysis": "Incomplete system information, please verify manually"
        }
    
    # Check if all env info fields have values
    if len(env_info) < 7 or any(not value for value in env_info[:7]):
        print(f"Warning: Incomplete environment info for index {index}")
        return {
            "is_sandbox": False,
            "confidence_score": 0,
            "analysis": "Incomplete environment information, please verify manually"
        }
    
    system_info = {
        'send_time': basic_info[0],
        'privilege': basic_info[1],
        'username': basic_info[2],
        'hostname': basic_info[3],
        'external_ip': basic_info[4],
        'core_num': env_info[0],
        'ram': env_info[1],
        'resolution': env_info[2],
        'current_path': env_info[3],
        'parent_process': env_info[4],
        'boot_time': env_info[5],
        'tempfile_num': env_info[6],
        'GPU_name': env_info[7],
        'GPU_memory': env_info[8],
    }
    
    return analyze_sandbox_environment(system_info) 