"""
Chat inference logic for ONNX models.

Uses optimum ORTModelForCausalLM + HuggingFace tokenizer.
apply_chat_template builds the prompt from messages[].
"""
import logging

logger = logging.getLogger("onnx_service.inference")


def chat_completion(
    model,
    tokenizer,
    messages: list,
    temperature: float = 0.7,
    max_new_tokens: int = 512,
) -> str:
    """Run a chat completion given an OpenAI-style messages list.

    Returns the assistant response text.
    """
    from transformers import GenerationConfig

    # Build prompt using the model's chat template
    try:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    except Exception:
        # Fallback: concatenate messages manually if no chat template
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(f"<|{role}|>\n{content}")
        parts.append("<|assistant|>\n")
        prompt = "\n".join(parts)

    inputs = tokenizer(prompt, return_tensors="pt")

    do_sample = temperature > 0.01
    gen_config = GenerationConfig(
        max_new_tokens=max_new_tokens,
        do_sample=do_sample,
        temperature=temperature if do_sample else 1.0,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

    try:
        output_ids = model.generate(**inputs, generation_config=gen_config)
    except Exception as e:
        logger.exception("Generation failed: %s", e)
        raise RuntimeError(f"Inference failed: {e}") from e

    # Decode only newly generated tokens (skip the prompt)
    prompt_len = inputs["input_ids"].shape[1]
    new_tokens = output_ids[0][prompt_len:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)
