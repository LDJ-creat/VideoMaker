export type TaskStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "retrying";

export type TaskStage =
  | "uploading"
  | "extracting_metadata"
  | "extracting_audio"
  | "transcribing"
  | "detecting_shots"
  | "extracting_keyframes"
  | "extracting_structure"
  | "analyzing_assets"
  | "mapping_slots"
  | "planning_completion"
  | "generating_storyboard"
  | "building_timeline"
  | "rendering"
  | "completed"
  | "running_agent"
  | "generating_material"
  | "generating_image"
  | "generating_video"
  | "generating_tts"
  | "rendering_material"
  | "parsing_edit_intent"
  | "applying_edit_intent";

export type ArtifactType =
  | "video"
  | "audio"
  | "image"
  | "json"
  | "text"
  | "html"
  | "render";

export type ArtifactRef = {
  id: string;
  type: ArtifactType;
  uri: string;
  createdAt: string;
};

export type ToolError = {
  code: string;
  message: string;
  retryable: boolean;
  details?: unknown;
};

export type TaskEvent = {
  taskId: string;
  status: TaskStatus;
  stage: TaskStage;
  progress: number;
  message: string;
  artifactRefs?: ArtifactRef[];
  error?: ToolError;
  updatedAt: string;
};

export type EditIntentTarget =
  | "generation_plan.storyboard"
  | "generation_plan.packaging"
  | "render_timeline"
  | "generation_params";

export type EditIntentOperation =
  | "adjust_hook"
  | "reduce_subtitles"
  | "increase_subtitles"
  | "reorder_selling_points"
  | "change_pace"
  | "change_packaging_style"
  | "adjust_cta";

export type EditIntentItem = {
  target: EditIntentTarget;
  operation: EditIntentOperation;
  params: Record<string, unknown>;
  rationale: string;
};

export type EditIntent = {
  intents: EditIntentItem[];
};

export type MaterialTemplate =
  | "benefit-card"
  | "title-lower-third"
  | "ken-burns"
  | "custom";

export type MaterialSpecParams = {
  title?: string;
  bullets?: string[];
  colors?: Record<string, unknown>;
  assetRefs?: ArtifactRef[];
  subtitle?: string;
};

export type MaterialSpec = {
  template: MaterialTemplate;
  durationSec: number;
  params: MaterialSpecParams;
};

export type AgentRunLog = {
  id: string;
  taskId?: string;
  generationId?: string;
  agentName: string;
  promptVersion: string;
  model: string;
  task: string;
  inputSummary: string;
  outputValid: boolean;
  validationErrors?: string[];
  latencyMs: number;
  tokenUsage?: { prompt: number; completion: number };
  createdAt: string;
};

export type VideoMetadata = {
  durationSec: number;
  width?: number;
  height?: number;
  fps?: number;
  codec?: string;
  hasAudio?: boolean;
};

export type NarrativeSegmentRole =
  | "hook"
  | "problem"
  | "solution"
  | "proof"
  | "benefit"
  | "comparison"
  | "cta"
  | "transition";

export type NarrativeSegment = {
  id: string;
  role: NarrativeSegmentRole;
  startSec: number;
  endSec: number;
  scriptSummary: string;
  visualSummary: string;
  intent: string;
};

export type NarrativeStructure = {
  summary: string;
  segments: NarrativeSegment[];
};

export type ShotChangeReason =
  | "visual_cut"
  | "scene_change"
  | "caption_change"
  | "beat"
  | "unknown";

export type ShotBoundary = {
  startSec: number;
  endSec: number;
  confidence: number;
  changeReason: ShotChangeReason;
};

export type RhythmProfile = {
  totalDurationSec: number;
  shotCount: number;
  avgShotDurationSec: number;
  tempo: "slow" | "medium" | "fast" | "mixed";
  climaxSec?: number;
  beatPoints: number[];
  shotBoundaries: ShotBoundary[];
};

export type LooseStyleObject = Record<string, unknown>;

export type PackagingProfile = {
  subtitleStyle?: LooseStyleObject;
  titleCards: LooseStyleObject[];
  stickers: LooseStyleObject[];
  transitions: LooseStyleObject[];
  coverStyle?: LooseStyleObject;
  visualDensity: "low" | "medium" | "high";
};

export type StructureSlotRole =
  | "hook_visual"
  | "hook_text"
  | "product_closeup"
  | "usage_scene"
  | "benefit_card"
  | "comparison"
  | "proof"
  | "transition"
  | "cta";

export type SlotRequiredAssetType =
  | "video"
  | "image"
  | "text"
  | "voiceover"
  | "generated_visual"
  | "packaging";

export type SlotImportance = "must_have" | "recommended" | "optional";

export type SlotConstraint = Record<string, unknown>;

export type StructureSlot = {
  id: string;
  segmentId: string;
  role: StructureSlotRole;
  startSec: number;
  endSec: number;
  requiredAssetType: SlotRequiredAssetType[];
  visualIntent: string;
  scriptIntent: string;
  packagingHint?: string;
  importance: SlotImportance;
  constraints: SlotConstraint[];
};

export type StructureEvidence = {
  targetId: string;
  source: "asr" | "ocr" | "keyframe" | "shot_detection" | "audio" | "llm";
  summary: string;
  confidence: number;
};

export type VideoStructure = {
  id: string;
  projectId: string;
  sourceVideoId: string;
  version: string;
  metadata: VideoMetadata;
  narrative: NarrativeStructure;
  rhythm: RhythmProfile;
  packaging: PackagingProfile;
  slots: StructureSlot[];
  evidence: StructureEvidence[];
  confidence: number;
};

export type UserBrief = {
  topic?: string;
  productName?: string;
  sellingPoints: string[];
  targetAudience?: string;
  tone?: string;
  mustMention: string[];
  avoidMention: string[];
};

export type UserAsset = {
  id: string;
  type: "video" | "image" | "text";
  uri: string;
  description?: string;
  tags?: string[];
  durationSec?: number;
};

export type ContentFact = {
  id: string;
  kind: "selling_point" | "audience" | "scene" | "constraint" | "other";
  text: string;
  source: string;
};

export type CandidateSegmentRole = "hook" | "mid" | "cta";

export type CandidateMoment = {
  id: string;
  assetId: string;
  startSec: number;
  endSec: number;
  description: string;
  tags: string[];
  visualTags?: string[];
  highlightScore?: number;
  suggestedSegmentRoles?: CandidateSegmentRole[];
};

export type AssetInventory = {
  id: string;
  projectId: string;
  userBrief: UserBrief;
  assets: UserAsset[];
  extractedFacts: ContentFact[];
  candidateMoments: CandidateMoment[];
};

export type CompletionStrategy =
  | "text_completion"
  | "packaging_completion"
  | "asset_reuse"
  | "hyperframes_material"
  | "image_generation"
  | "video_generation"
  | "tts";

export type CompletionProvider =
  | "asset_reuse"
  | "hyperframes_material"
  | "image_generation"
  | "video_generation"
  | "tts"
  | "text_completion"
  | "packaging_completion";

export type SlotMatch = {
  slotId: string;
  assetId?: string;
  momentId?: string;
  matchScore: number;
  matchReason: string;
};

export type MissingSlot = {
  slotId: string;
  reason: string;
  impact: "low" | "medium" | "high";
  suggestedFixes: CompletionStrategy[];
};

export type WeakSlot = MissingSlot;

export type GapReport = {
  id: string;
  projectId: string;
  structureId: string;
  inventoryId: string;
  slotMatches: SlotMatch[];
  missingSlots: MissingSlot[];
  weakSlots: WeakSlot[];
  summary: string;
};

export type TimelineTrackType =
  | "video"
  | "image"
  | "text"
  | "voiceover"
  | "bgm"
  | "effect"
  | "transition";

export type ClipTransform = {
  x?: number;
  y?: number;
  scale?: number;
  rotation?: number;
  opacity?: number;
};

export type GeneratedBy = {
  provider: string;
  model?: string;
  promptVersion?: string;
  template?: string;
};

export type TimelineClip = {
  id: string;
  startSec: number;
  endSec: number;
  sourceRef?: string;
  content?: string;
  styleRef?: string;
  transform?: ClipTransform;
  generatedBy?: string | GeneratedBy;
};

export type TimelineTrack = {
  id: string;
  type: TimelineTrackType;
  clips: TimelineClip[];
};

export type RenderTimeline = {
  durationSec: number;
  tracks: TimelineTrack[];
};

export type GenerationVariant =
  | "default"
  | "high_click"
  | "high_conversion"
  | "fast_paced"
  | "premium";

export type StoryboardScene = {
  id: string;
  slotId: string;
  startSec: number;
  endSec: number;
  visual: string;
  script: string;
  source:
    | "user_asset"
    | "text_completion"
    | "packaging_completion"
    | "asset_reuse"
    | "generated";
};

export type PackagingPlan = {
  styleSummary: string;
  subtitle: LooseStyleObject;
  titleCards: LooseStyleObject[];
  transitions: LooseStyleObject[];
};

export type CompletionAction = {
  id: string;
  slotId: string;
  strategy: CompletionStrategy;
  reason: string;
  outputRef: string;
  provider?: CompletionProvider;
  rationale?: string;
  artifactRef?: ArtifactRef;
};

export type GenerationPlan = {
  id: string;
  projectId: string;
  structureId: string;
  inventoryId: string;
  gapReportId: string;
  variant: GenerationVariant;
  storyboard: StoryboardScene[];
  timeline: RenderTimeline;
  packagingPlan: PackagingPlan;
  completionActions: CompletionAction[];
};
