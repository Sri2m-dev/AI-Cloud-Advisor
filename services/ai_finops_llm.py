from openai import OpenAI
import pandas as pd
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_ai_recommendations(cost_df):
    cost_summary = cost_df.to_string()
    prompt = f"""
You are a FinOps cloud cost optimization expert.

Analyze the following AWS cost breakdown and suggest
cost optimization recommendations.

Cost Data:
{cost_summary}

Provide clear recommendations with estimated savings.
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a FinOps expert."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content
