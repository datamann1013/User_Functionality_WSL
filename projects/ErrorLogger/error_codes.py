# Error code definitions for ErrorLogger and all project components
# Convention: [Type][Origin][Component][Subcomponent][Number]
# Example: EABS1 = Error, AI Service, Backend, Setup Model, 1

ERROR_CODE_DEFINITIONS = {
    # ===== Standard Errors =====
    "E00000": "Python exception occurred (standard)",
    "E00001": "React exception occurred (standard)",
    "EREM1": "Remote logger failed (standard)",
    # ===== Setup/Model =====
    "IABS1": "Setup model script started",
    "IABS2": "All required model files present",
    "IABS3": "Model file downloaded successfully",
    "IABS4": "Using Hugging Face Hub API for download",
    "IABS5": "Gated model access detected",
    "EABS1": "Missing required model files",
    "EABS2": "Failed to download model file",
    "EABS3": "Missing Hugging Face access token",
    # ===== Model Registry Errors =====
    "EMR01": "Failed to load model registry",
    "EMR02": "Failed to save model registry",
    "EMR03": "Failed to list models",
    "EMR04": "Model not found",
    "EMR05": "Failed to retrieve model details",
    "EMR06": "Invalid model data format",
    "EMR07": "Model ID already exists",
    "EMR08": "Failed to save new model",
    "EMR09": "Failed to add model to registry",
    "EMR10": "Invalid update data",
    "EMR11": "Model not found for update",
    "EMR12": "Failed to save model update",
    "EMR13": "Failed to update model",
    "EMR14": "Model not found for deletion",
    "EMR15": "Failed to save after deletion",
    "EMR16": "Failed to delete model",
    # ===== Backend/Inference =====
    "IABB1": "Inference request received",
    "IABB2": "Inference response sent",
    "EABB1": "Inference failed - model loading issue",
    "EABB2": "No available model for inference",
    "EABB3": "Model loading failed - unsupported format",
    "EABB4": "Inference timeout",
    "EABB5": "Upstream AI service unavailable or unresponsive",
    "IABS6": "Model loaded successfully",
    # ===== Frontend =====
    "IAFX1": "Frontend transmission received",
    "IAFX2": "Frontend transmission sent",
    "EAFX1": "Frontend error occurred",
    # ===== Health/Info =====
    "IAXX1": "Health check called",
    # ===== Add new codes below =====
}
