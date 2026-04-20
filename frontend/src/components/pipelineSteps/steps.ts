/** Data + type for the 12-step pipeline narrative. */
import type { ComponentType } from "react";

import {
  VisualBaseline,
  VisualChallenges,
  VisualDecompose,
  VisualResearch,
  VisualSeed,
  VisualSelect,
} from "./foundationVisuals";
import {
  VisualAssemble,
  VisualBreed,
  VisualCompete,
  VisualScore,
  VisualShip,
  VisualSpawn,
} from "./loopVisuals";

export interface Step {
  number: number;
  title: string;
  description: string;
  metric: string;
  isLoop?: boolean;
  visual: ComponentType;
}

export const STEPS: Step[] = [
  {
    number: 1,
    title: "Research Domain",
    description: "Analyze the target ecosystem for skill families worth evolving",
    metric: "34 candidates identified",
    visual: VisualResearch,
  },
  {
    number: 2,
    title: "Select Lighthouse Families",
    description: "Rank by community impact, complexity, and LLM failure rate",
    metric: "7 families selected",
    visual: VisualSelect,
  },
  {
    number: 3,
    title: "Decompose into Capabilities",
    description: "Break each skill into atomic, independently-evolvable dimensions",
    metric: "83 dimensions total",
    visual: VisualDecompose,
  },
  {
    number: 4,
    title: "Generate SKLD-bench Challenges",
    description: "Author challenges per tier: easy, medium, hard, legendary",
    metric: "867 challenges authored",
    visual: VisualChallenges,
  },
  {
    number: 5,
    title: "Run Baselines",
    description: "Score raw Sonnet with no skill guidance to establish the floor",
    metric: "93.3% L0, 51.1% composite",
    visual: VisualBaseline,
  },
  {
    number: 6,
    title: "Research & Create Seed Skill",
    description: "Build a golden-template package: SKILL.md + scripts + references",
    metric: "7 seed packages",
    visual: VisualSeed,
  },
  {
    number: 7,
    title: "Spawn Variants",
    description: "Generate diverse alternatives per dimension",
    metric: "2 variants x 12 dimensions",
    isLoop: true,
    visual: VisualSpawn,
  },
  {
    number: 8,
    title: "Compete",
    description: "Run both variants against sampled challenges from the bench",
    metric: "4 dispatches per dimension",
    isLoop: true,
    visual: VisualCompete,
  },
  {
    number: 9,
    title: "Score",
    description: "L0 string match + Compile + AST + Behavioral = composite fitness",
    metric: "6-layer composite scorer",
    isLoop: true,
    visual: VisualScore,
  },
  {
    number: 10,
    title: "Judge & Breed",
    description: "Pick winners, mutate losers based on execution traces",
    metric: "Repeat N generations",
    isLoop: true,
    visual: VisualBreed,
  },
  {
    number: 11,
    title: "Assemble Composite",
    description: "Merge winning variants from all dimensions into one skill",
    metric: "1 composite package",
    visual: VisualAssemble,
  },
  {
    number: 12,
    title: "Ship",
    description: "Install test, extract findings to the Bible, publish to Registry",
    metric: "7/7 positive skill lift",
    visual: VisualShip,
  },
];
