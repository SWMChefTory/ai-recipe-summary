import { Mastra } from "@mastra/core";
import { Memory } from "@mastra/memory";
import { InMemoryStore } from "@mastra/core/storage";
import { recipeExtractor } from "./agents/recipe-extractor";
import { recipeExtractionWorkflow } from "./workflows/recipe-extraction";

const storage = new InMemoryStore();
const memory = new Memory();

export const mastra = new Mastra({
  agents: {
    recipeExtractor,
  },
  workflows: {
    "recipe-extraction": recipeExtractionWorkflow,
  },
  storage,
  memory: {
    default: memory,
  },
});
