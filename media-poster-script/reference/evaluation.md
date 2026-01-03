# Evaluation Guide

This guide explains how to create effective evaluations for MCP servers using script-based testing.

## Evaluation Purpose

Use evaluations to verify that LLMs can effectively use your MCP server to answer realistic, complex questions.

## Creating 10 Evaluation Questions

Follow this process:

### Step 1: Tool Inspection

List all available tools and understand their capabilities:

```bash
python scripts/tool_caller.py --command "python" --args "server.py" --list-tools
```

### Step 2: Content Exploration

Use read-only operations to explore the data and understand what information is available.

### Step 3: Question Generation

Create 10 questions following these rules:

**Each question must be:**
- **Independent**: Not dependent on other questions
- **Read-only**: Only non-destructive operations required
- **Complex**: Requiring multiple tool calls or deep exploration
- **Realistic**: Based on real use cases humans would care about
- **Verifiable**: Single, clear answer that can be verified
- **Stable**: Answer won't change over time

**Question templates:**

```xml
<!-- Factual retrieval -->
<qa_pair>
  <question>What is the title of movie ID 123?</question>
  <answer>Inception</answer>
</qa_pair>

<!-- Counting -->
<qa_pair>
  <question>How many action movies were released in 2020?</question>
  <answer>15</answer>
</qa_pair>

<!-- Filtering -->
<qa_pair>
  <question>List all movies with rating above 4.5</question>
  <answer>3</answer>
</qa_pair>

<!-- Aggregation -->
<qa_pair>
  <question>What is the average rating of all sci-fi movies?</question>
  <answer>4.2</answer>
</qa_pair>

<!-- Lookup with specific detail -->
<qa_pair>
  <question>Find the director of the highest-rated movie from 2019</question>
  <answer>Christopher Nolan</answer>
</qa_pair>
```

### Step 4: Answer Verification

Solve each question yourself to verify answers are correct:

1. Use the tools manually
2. Record the expected answer
3. Ensure the answer format matches what the LLM will produce

## Output Format

Create an XML file with this structure:

```xml
<evaluation>
  <qa_pair>
    <question>Your question here</question>
    <answer>Expected answer here</answer>
  </qa_pair>
  <!-- Add 9 more qa_pairs -->
</evaluation>
```

## Running an Evaluation

```bash
# With stdio transport
python scripts/evaluation.py \
  --command python \
  --args media_poster_server.py \
  --eval evaluation.xml

# With output report
python scripts/evaluation.py \
  --command python \
  --args server.py \
  --eval evaluation.xml \
  --output evaluation_report.md
```

## Evaluation Metrics

The evaluation report includes:

- **Accuracy**: Percentage of correct answers
- **Average Duration**: Mean time per question
- **Tool Calls**: Number of tool invocations
- **Per-question breakdown**: Detailed results for each question

## Example Questions

See `assets/example_evaluation.xml` for a complete example.

## Best Practices

1. **Start simple**: Begin with straightforward questions
2. **Add complexity**: Progress to multi-step questions
3. **Cover edge cases**: Test error conditions
4. **Be specific**: Clear, unambiguous questions
5. **Verify independence**: Ensure each question works alone

## Common Mistakes

❌ **Dependent questions**:
```xml
<!-- BAD: Question 2 depends on Question 1's result -->
<qa_pair><question>List movies</question><answer>...</answer></qa_pair>
<qa_pair><question>What is the first movie?</question><answer>...</answer></qa_pair>
```

❌ **Ambiguous answers**:
```xml
<!-- BAD: Multiple valid answers or unclear format -->
<qa_pair>
  <question>What movies are popular?</question>
  <answer>It depends on the definition of popular</answer>
</qa_pair>
```

✅ **Independent, specific answers**:
```xml
<qa_pair>
  <question>What is the title of movie ID 456?</question>
  <answer>The Shawshank Redemption</answer>
</qa_pair>
```
