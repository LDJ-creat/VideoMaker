import type { VideoMetadata } from "./types";

export type SampleAudioProfile = {
  hasVoiceover: boolean;
  hasBgm: boolean;
  silenceRegions: { startSec: number; endSec: number }[];
  speechRegions: { startSec: number; endSec: number; textPreview?: string }[];
  bgmCandidateRegions: { startSec: number; endSec: number }[];
  energyTimeline: { timeSec: number; rmsDb: number }[];
  onsetTimes: number[];
  tempoBpm?: number;
  metrics: {
    voiceoverCoveragePct: number;
    silenceCoveragePct: number;
    bgmBedLikely: boolean;
  };
};

export type OnScreenTextFact = {
  timeSec: number;
  keyframePath: string;
  text: string;
  confidence: number;
};

export type KeyframeBatchDigest = {
  batchIndex: number;
  startSec: number;
  endSec: number;
  frames: { shotId?: string; timeSec?: number; path?: string }[];
  visualFacts: string;
  onScreenTextFacts: OnScreenTextFact[];
};

export type SampleAnalysisFacts = {
  metadata: VideoMetadata;
  transcript: unknown;
  shots: unknown[];
  keyframes: unknown[];
  audioProfile?: SampleAudioProfile;
  keyframeBatchDigests?: KeyframeBatchDigest[];
  onScreenTextFacts?: OnScreenTextFact[];
  analysisDepth?: "fast" | "standard" | "deep";
  locale?: string;
  warnings?: string[];
};
