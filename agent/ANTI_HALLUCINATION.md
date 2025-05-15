# Anti-Hallucination System for Eliza

This guide explains how to use and extend the anti-hallucination features integrated into the Eliza agent system. These features help prevent hallucinations (fabricated information) in AI responses by grounding agent outputs in factual knowledge and implementing verification mechanisms.

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Directory Structure](#directory-structure)
4. [Integration Guide](#integration-guide)
5. [Configuration Options](#configuration-options)
6. [Creating Knowledge Files](#creating-knowledge-files)
7. [Customizing Per Character](#customizing-per-character)
8. [Adding New Characters](#adding-new-characters)
9. [Extending the System](#extending-the-system)
10. [Troubleshooting](#troubleshooting)

## Overview

The anti-hallucination system uses multiple techniques to reduce the likelihood of AI agents providing incorrect or fabricated information:

1. **Retrieval Augmented Generation (RAG)**: Provides factual context from knowledge files
2. **Fact-Checking Evaluator**: Identifies and flags potentially hallucinated content
3. **System Prompt Enhancements**: Instructs the model to express uncertainty appropriately
4. **Temperature Control**: Adjusts model creativity/factuality balance
5. **Character-Specific Knowledge**: Maintains separate knowledge bases for each character

## Features

- **Character-Agnostic**: Works with any character in your Eliza ecosystem
- **Plugin-Compatible**: Doesn't interfere with any plugin functionality
- **Configurable**: Adjust settings for individual characters or globally
- **Extensible**: Easy to add more knowledge or customize evaluator behavior
- **Multi-Character Support**: Each character can have their own knowledge base
- **Dynamic Response Handling**: Adapts to each character's conversation style

## Directory Structure

```
agent/
├── knowledge/              # Root knowledge directory
│   ├── facts.md           # General knowledge for all characters
│   ├── Character1/        # Character-specific knowledge folders
│   │   └── file1.md
│   ├── Character2/
│   │   └── file2.md
│   └── ...
├── src/
    ├── evaluators/        # Contains evaluator components
    │   ├── index.ts
    │   └── factCheckEvaluator.ts
    ├── services/          # Contains service components
    │   ├── index.ts
    │   └── ragService.ts
    └── config/
        └── antiHallucination.ts  # Configuration settings
```

## Integration Guide

To integrate anti-hallucination features with your Eliza agent:

### 1. Start with Multiple Characters

```bash
# Start Eliza with multiple characters
elizaos start --characters=./characters/character1.character.json,./characters/character2.character.json
```

The system will automatically:
- Apply the anti-hallucination prompts
- Load appropriate knowledge bases
- Setup fact-checking evaluators
- Create character-specific knowledge directories if they don't exist

### 2. Using with Docker

If you're using Docker, all the anti-hallucination features are already integrated. Just make sure your volume mounts include the knowledge directory:

```yaml
volumes:
  - ./data:/app/data
  - ./knowledge:/app/knowledge
```

## Configuration Options

You can customize the anti-hallucination behavior in `src/config/antiHallucination.ts`:

```typescript
// Default configuration (applied to all characters)
const defaultConfig: AntiHallucinationConfig = {
  useFactChecking: true,    // Enable/disable fact checking evaluator
  useRAG: true,             // Enable/disable knowledge retrieval
  temperature: 0.7,         // Model temperature (lower = more factual)
  systemPromptAddition: "..." // Anti-hallucination prompt addition
};

// Character-specific configurations
const characterConfigs: Record<string, Partial<AntiHallucinationConfig>> = {
  "CharacterName": {
    temperature: 0.5,       // Override for this character
    // Other overrides...
  }
};
```

## Creating Knowledge Files

Knowledge files are Markdown (`.md`) documents containing factual information:

1. **General Knowledge**: Place files in the root `/knowledge/` directory
2. **Character-Specific Knowledge**: Place files in `/knowledge/CharacterName/`

Example knowledge file structure:

```markdown
# Topic Title

This is an introduction to the topic.

## Subtopic 1

- Fact 1 about the subtopic
- Fact 2 about the subtopic

## Subtopic 2

- Another fact
- Yet another fact
```

## Customizing Per Character

### System Prompts

Each character can have a custom anti-hallucination prompt by adding to their configuration in `antiHallucination.ts`:

```typescript
"CharacterName": {
  systemPromptAddition: "Custom instructions for preventing hallucinations..."
}
```

### Fact-Checking Behavior

The fact-checking evaluator can be customized for specific characters:

```typescript
this.characterConfigs.set("CharacterName", {
  riskPhrases: [...this.config.riskPhrases, "additional", "phrases"],
  safetyPhrases: [...this.config.safetyPhrases, "more", "phrases"],
  warningMessage: "Custom warning message for this character"
});
```

## Adding New Characters

New characters automatically benefit from anti-hallucination features. To optimize:

1. Create the character JSON file in `/characters/`
2. Create a knowledge directory at `/knowledge/CharacterName/`
3. Add character-specific configuration in `antiHallucination.ts` if needed
4. Add specific fact-checking behavior if desired

## Extending the System

### Adding Custom Evaluators

Create new evaluators in the `/src/evaluators/` directory:

```typescript
export class CustomEvaluator implements Evaluator {
  id: string = "custom-evaluator";
  name: string = "Custom Evaluator";
  
  async evaluate(message: Message, character?: Character): Promise<Message> {
    // Custom evaluation logic
    return message;
  }
}
```

### Enhancing RAG Capabilities

You can extend the RAG service by modifying `/src/services/ragService.ts`:

- Add more sophisticated search algorithms
- Implement vector embeddings for semantic search
- Add support for different file formats
- Integrate external knowledge bases

## Troubleshooting

### Character Not Using Knowledge

If a character isn't using its knowledge base:

1. Check that the knowledge directory exists (`/knowledge/CharacterName/`)
2. Verify RAG is enabled for that character in configuration
3. Ensure the character's name in the JSON file matches the directory name exactly (case-sensitive)
4. Check the logs for any errors loading knowledge files

### Fact-Checking Not Working

If the fact-checking evaluator isn't flagging hallucinations:

1. Verify fact-checking is enabled in configuration
2. Check that the risk phrases match the character's speaking style
3. Make sure the character is properly loaded and registered

### General Issues

For general issues with the anti-hallucination system:

1. Check the logs for any error messages
2. Restart the Eliza service
3. Verify all files and directories have proper permissions
4. Ensure character configurations are correctly formatted

## More Information

For more details about the Eliza agent system, refer to the main [README.md](./README.md) and the [official Eliza documentation](https://docs.eliza.how/).