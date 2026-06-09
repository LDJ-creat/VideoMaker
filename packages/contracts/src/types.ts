export type TaskStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "retrying"
  | "awaiting_review";

export type TaskStage =
  | "uploading"
  | "extracting_metadata"
  | "extracting_audio"
  | "transcribing"
  | "analyzing_audio"
  | "detecting_shots"
  | "extracting_keyframes"
  | "extracting_visual_facts"
  | "consolidating"
  | "extracting_structure"
  | "extracting_structure_direct"
  | "analyzing_segments"
  | "compiling_structure"
  | "critiquing_structure"
  | "rendering_knowledge_draft"
  | "analyzing_assets"
  | "mapping_slots"
  | "drafting_master_script"
  | "awaiting_master_review"
  | "drafting_storyboard"
  | "awaiting_storyboard_review"
  | "producing_media"
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
  | "custom"
  | "composition";

export type CompositionFragment = {
  bodyHtml: string;
  styles?: string;
  timelineScript?: string;
  registryBlocks?: string[];
};

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
  params?: MaterialSpecParams;
  composition?: CompositionFragment;
};

export type KnowledgeEntryKind = "structure" | "composition_pattern";

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
  transcriptExcerpt?: string;
  rhetoricalDevices?: string[];
  emotionTone?: string;
  retentionRole?: string;
  voStyle?: { pace: string; energy: string; persona: string };
  visualSpec?: {
    framing: string;
    subject: string;
    cameraMove: string;
    onScreenText: string[];
    colorMood: string;
    density: "low" | "medium" | "high";
  };
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
  durationSharePct?: number;
  migrationTemplate?: string;
  packagingRequirements?: string[];
  antiPatterns?: string[];
};

export type StructureEvidence = {
  targetId: string;
  source: "asr" | "ocr" | "keyframe" | "shot_detection" | "audio" | "llm";
  summary: string;
  confidence: number;
  timeRange?: { startSec: number; endSec: number };
  excerpt?: string;
  artifactRef?: string;
};

export type AnalysisQuality = {
  warnings: string[];
  locale: string;
  promoteReady: boolean;
};

export type StructureContext = {
  contentCategory: ContentCategory;
  platformFormat: string;
  primaryIntent: "exposure" | "consideration" | "conversion";
  successHypothesis: string;
  applicability: {
    suitableFor: string[];
    unsuitableFor: string[];
  };
};

export type VerbalOutlinePhase = {
  phase: string;
  startSec: number;
  endSec: number;
  sharePct: number;
};

export type VerbalLayer = {
  hookTemplate: string;
  outlineTimeline: VerbalOutlinePhase[];
  ctaMechanism: string;
  infoLubricantRatio?: {
    infoSec: number;
    lubricantSec: number;
    ratio: number;
  };
};

export type ConceptVisualMapEntry = {
  concept: string;
  visualMetaphor: string;
  timeSec?: number;
  assetHint?: string;
};

export type CutRateProfile = {
  avgShotSec?: number;
  openingCutRate?: string;
  fastCutRanges?: { startSec: number; endSec: number }[];
};

export type VisualPackagingSpec = {
  visualDensity?: "low" | "medium" | "high";
  summary?: string;
} & LooseStyleObject;

export type VisualLayer = {
  conceptVisualMap?: ConceptVisualMapEntry[];
  cutRateProfile?: CutRateProfile;
  packagingSpec?: VisualPackagingSpec;
};

export type StructureVoProfile = {
  pace?: string;
  energy?: string;
  persona?: string;
  wordsPerMinute?: number;
};

export type AudioEventRule = {
  trigger: string;
  action: string;
  timeSec?: number;
};

export type StructureAudioLayer = {
  voProfile?: StructureVoProfile;
  audioEventRules?: AudioEventRule[];
};

export type EmotionTrigger = {
  timeSec: number;
  triggerType: string;
  segmentId: string;
  mechanism: string;
};

export type TransferMetadata = {
  structureFamily: string;
  differentiationLever: string;
  emotionTriggers: EmotionTrigger[];
  scalabilityRules: string;
  nonTransferableElements: string[];
  materialRequirementsSummary?: string;
};

export type VideoStructureVersion = "p1-v3";

export type VideoStructure = {
  id: string;
  projectId: string;
  sourceVideoId: string;
  version: VideoStructureVersion;
  metadata: VideoMetadata;
  context: StructureContext;
  verbal: VerbalLayer;
  visual?: VisualLayer;
  audio?: StructureAudioLayer;
  transfer: TransferMetadata;
  narrative: NarrativeStructure;
  rhythm: RhythmProfile;
  slots: StructureSlot[];
  evidence: StructureEvidence[];
  confidence: number;
  analysisQuality: AnalysisQuality;
};

export type ContentCategory =
  | "product_commerce"
  | "education"
  | "vlog_lifestyle"
  | "brand_story"
  | "tutorial"
  | "entertainment"
  | "news_commentary"
  | "general";

export type DurationTargetSource = "sample" | "user" | "default";

export type DurationTarget = {
  targetSec: number;
  minSec?: number;
  maxSec?: number;
  recommendedSec?: number;
  source?: DurationTargetSource;
};

export type GenerationStrategy = "short_form_direct" | "long_form_composed";

export type AspectRatio = "9:16" | "16:9" | "1:1";

export type ScriptReviewStatus = "draft" | "approved";

export type UserBrief = {
  contentCategory?: ContentCategory;
  topic?: string;
  creativeGoal?: string;
  subjectName?: string;
  /** @deprecated use subjectName */
  productName?: string;
  keyPoints?: string[];
  sellingPoints: string[];
  targetAudience?: string;
  tone?: string;
  mustMention: string[];
  avoidMention: string[];
  supplementalNotes?: string;
  durationTarget?: DurationTarget;
  aspectRatio?: AspectRatio;
};

export type UserAsset = {
  id: string;
  type: "video" | "image" | "text";
  uri: string;
  description?: string;
  tags?: string[];
  durationSec?: number;
};

export type ContentFactKind =
  | "selling_point"
  | "key_message"
  | "goal"
  | "audience"
  | "scene"
  | "constraint"
  | "other";

export type ContentFact = {
  id: string;
  kind: ContentFactKind;
  text: string;
  source: string;
};

export type AssetUnderstandingRoute =
  | "direct_multimodal"
  | "legacy"
  | "direct_multimodal_batched";

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
  assetUnderstandingRoute?: AssetUnderstandingRoute;
  assetUnderstandingWarnings?: string[];
  userBrief: UserBrief;
  assets: UserAsset[];
  extractedFacts: ContentFact[];
  candidateMoments: CandidateMoment[];
};

export type CompletionStrategy =
  | "text_completion"
  | "packaging_completion"
  | "asset_reuse"
  | "stock_media_search"
  | "hyperframes_material"
  | "image_generation"
  | "video_generation"
  | "tts";

export type CompletionProvider =
  | "asset_reuse"
  | "stock_media_search"
  | "hyperframes_material"
  | "image_generation"
  | "video_generation"
  | "tts"
  | "text_completion"
  | "packaging_completion";

export type StockSearchQuery = {
  primaryQuery: string;
  fallbackQueries: string[];
  locale: "en";
  negativeTerms?: string[];
  preferVideo?: boolean;
  orientation?: "landscape" | "portrait" | "square";
};

export type StockAttribution = {
  source: "pexels";
  mediaId: number;
  pageUrl: string;
  photographer: string;
  query: string;
  mediaType?: "photo" | "video";
};

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
  source?: string;
  photographer?: string;
  pageUrl?: string;
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
  stockSearchQuery?: StockSearchQuery;
  stockAttribution?: StockAttribution;
};

export type GenerationPlan = {
  id: string;
  projectId: string;
  structureId: string;
  inventoryId: string;
  gapReportId: string;
  variant: GenerationVariant;
  generationStrategy?: GenerationStrategy;
  durationTargetSec?: number;
  aspectRatio?: AspectRatio;
  ttsMode?: "global" | "per_scene";
  narrationDurationSec?: number;
  masterNarration: string;
  storyboard: StoryboardScene[];
  timeline: RenderTimeline;
  packagingPlan: PackagingPlan;
  completionActions: CompletionAction[];
};

export type ScriptDraft = {
  generationId: string;
  projectId: string;
  variant: GenerationVariant;
  masterNarration: string;
  masterNarrationStatus: ScriptReviewStatus;
  storyboard: StoryboardScene[];
  storyboardStatus: ScriptReviewStatus;
  generationStrategy?: GenerationStrategy;
  durationTargetSec?: number;
  masterApprovedAt?: string;
  storyboardApprovedAt?: string;
  approvedBy?: string;
};

export type KnowledgeEntryStatus = "draft" | "published" | "archived";

export type KnowledgeEntry = {
  id: string;
  status: KnowledgeEntryStatus;
  entryKind?: KnowledgeEntryKind;
  title: string;
  category: string;
  categorySlug?: string;
  style: string;
  hookType?: string;
  tempo?: "slow" | "medium" | "fast" | "mixed";
  durationBucket?: string;
  slotPattern: string;
  summary: string;
  skillMdUri: string;
  structureJsonUri: string;
  sourceProjectId?: string;
  sourceSampleId?: string;
  version: number;
  createdAt: string;
  updatedAt: string;
};

export type KnowledgeRecommendationCandidate = {
  entryId: string;
  score: number;
  reasons: string[];
  entry: KnowledgeEntry;
};

export type KnowledgeRecommendation = {
  projectId: string;
  candidates: KnowledgeRecommendationCandidate[];
  suggestedPrimaryId: string;
  computedAt: string;
};

export type KnowledgeCategorySummary = {
  category: string;
  categorySlug: string;
  entryCount: number;
  summary: string;
  coverUrl?: string | null;
  slotPatterns: string[];
  updatedAt: string;
};

export type KnowledgeCategoryEntryCard = {
  entryId: string;
  title: string;
  summary: string;
  style: string;
  slotPattern: string;
  hookType?: string;
  tempo?: "slow" | "medium" | "fast" | "mixed";
  durationBucket?: string;
  sourceProjectId?: string;
  sourceSampleId?: string;
  posterUrl?: string | null;
  previewUrl?: string | null;
  importable: boolean;
  importBlockReason?: string;
};

export type KnowledgeCategoryDetail = {
  category: string;
  categorySlug: string;
  entries: KnowledgeCategoryEntryCard[];
};

export type CreateProjectFromKnowledgeTemplateRequest = {
  name: string;
  categorySlug: string;
  primaryEntryId: string;
  referenceEntryIds?: string[];
};

export type KnowledgeTemplateImportedSample = {
  sampleId: string;
  entryId: string;
  title?: string;
};

export type CreateProjectFromKnowledgeTemplateResponse = {
  project: {
    id: string;
    name: string;
    createdAt: string;
  };
  importedSamples: KnowledgeTemplateImportedSample[];
  sampleSelection: ProjectSampleSelection;
  knowledgeSelection: ProjectKnowledgeSelection;
};

export type ProjectSummary = {
  id: string;
  name: string;
  createdAt: string;
  coverUrl?: string | null;
};

export type ProjectKnowledgeSelectionMode = "auto" | "user_override" | "none";

export type ProjectKnowledgeSelection = {
  projectId: string;
  primaryEntryId: string | null;
  referenceEntryIds: string[];
  mode: ProjectKnowledgeSelectionMode;
  appliedAsStructure: boolean;
  recommendationSnapshot?: KnowledgeRecommendation;
  updatedAt: string;
};

export type KnowledgeSkillOutput = {
  frontmatter: {
    title: string;
    category: string;
    style: string;
    hookType?: string;
    tempo?: "slow" | "medium" | "fast" | "mixed";
    durationBucket?: string;
    slotPattern?: string;
    summary: string;
    [key: string]: unknown;
  };
  markdown: string;
};

export type CompositionPatternPromoteOutput = {
  frontmatter: {
    title: string;
    category: string;
    summary: string;
    slotRoles: string[];
    motionPattern: string;
    [key: string]: unknown;
  };
  markdown: string;
  materialSpec: MaterialSpec;
};

export type CompositionPatternCandidate = {
  slotId: string;
  slotRole: string;
  storyboardSummary: string;
  actionId?: string | null;
  draftReady: boolean;
  publishedEntry?: {
    id: string;
    title?: string;
    updatedAt?: string;
  } | null;
};

export type UploadBatchStatus = "uploading" | "complete" | "partial_failed";

export type UploadBatch = {
  id: string;
  projectId: string;
  status: UploadBatchStatus;
  sampleIds: string[];
  createdAt: string;
  updatedAt: string;
};

export type SampleRecommendationCandidate = {
  sampleId: string;
  score: number;
  reasons: string[];
  summary?: string;
  uploadBatchId?: string | null;
  hasStructure: boolean;
  status: string;
};

export type SampleRecommendation = {
  projectId: string;
  candidates: SampleRecommendationCandidate[];
  suggestedPrimaryId: string;
  suggestedReferenceIds: string[];
  computedAt: string;
};

export type ProjectSampleSelectionMode = "auto" | "user_override" | "none";

export type ProjectSampleSelection = {
  projectId: string;
  primarySampleId: string | null;
  referenceSampleIds: string[];
  activeUploadBatchId?: string | null;
  mode: ProjectSampleSelectionMode;
  recommendationSnapshot?: SampleRecommendation;
  updatedAt: string;
};

export type StructureProvenanceSlotAttribution = {
  slotId: string;
  sourceSampleId: string;
  sourceSlotId?: string;
  rationale: string;
};

export type StructureProvenanceSegmentAttribution = {
  segmentId: string;
  sourceSampleId: string;
  rationale: string;
};

export type StructureProvenance = {
  id: string;
  projectId: string;
  generationRunId: string;
  primarySampleId: string;
  referenceSampleIds: string[];
  slotAttribution: StructureProvenanceSlotAttribution[];
  segmentAttribution?: StructureProvenanceSegmentAttribution[];
  synthesizerModel?: string;
  fallback?: boolean;
  createdAt: string;
};

export type GenerationRunStatus = "running" | "completed" | "partial_failed";

export type GenerationRun = {
  id: string;
  projectId: string;
  sampleSelectionSnapshot: ProjectSampleSelection;
  synthesizedStructureId?: string | null;
  provenanceId?: string | null;
  variantIds: string[];
  generationIds: string[];
  status: GenerationRunStatus;
  createdAt: string;
  updatedAt: string;
};

export type SampleSelectionOverride = {
  primarySampleId: string;
  referenceSampleIds?: string[];
};
