from openai import OpenAI

client = OpenAI()

def get_ai_recommendation(cost_data):
    """
    Analyze AWS cost data and return optimization suggestions using GPT-4o-mini.
    """
    prompt = f"""
    Analyze this AWS cost data and suggest optimizations:
    {cost_data}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
