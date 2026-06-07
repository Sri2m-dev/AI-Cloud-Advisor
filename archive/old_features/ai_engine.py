from openai import OpenAI

client = OpenAI()

def get_ai_recommendation(cost_data):
    prompt = f"""
    Analyze this AWS cost data and suggest optimizations:
    {cost_data}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

