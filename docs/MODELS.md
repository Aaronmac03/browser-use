Local LLM is primary executor. Must work on macbook pro m4 16b ram
Smart LLM via API call for planner and to interpret/rephrase ambiguous user prompt (openai o3).
inexpensive fallback executor (gemini flash 2.0 experimental or gemini flash 2.5) if local LLM fails
consider a critic if needed (gemini or o3)
consider an online LLM to summarize the output for the user (o3 or gemini flash)
consider smart model selector based on complexity of task
Cost and capabality are important factors in selecting models. speed is not as important.