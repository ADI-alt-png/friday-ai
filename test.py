from groq import Groq

client = Groq(api_key="YOUR_GROQ_API_KEY")

try:
    res = client.chat.completions.create(
       model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "hello"}]
    )
    print(res.choices[0].message.content)

except Exception as e:
    print("ERROR:", e)