import type { ModelGatewayStatusResponse } from "@/lib/apiClient";

export const fixtureModelGatewayStatus: ModelGatewayStatusResponse = {
  fixtureMode: true,
  providers: {
    text: {
      configured: true,
      hasApiKey: true,
      model: "gpt-4o",
      driver: "openai_compatible",
      baseUrl: "https://api.openai.com/v1",
    },
    vision: {
      configured: true,
      hasApiKey: true,
      model: "gpt-4o",
      driver: "openai_compatible",
      baseUrl: "https://api.openai.com/v1",
    },
    videoUnderstanding: {
      configured: false,
      hasApiKey: false,
      model: undefined,
      driver: "openai_compatible",
      baseUrl: "https://ark.cn-beijing.volces.com/api/v3",
    },
    tts: {
      configured: false,
      hasApiKey: false,
      model: undefined,
      driver: "openai_compatible",
      baseUrl: "https://api.openai.com/v1",
    },
    image: {
      configured: true,
      hasApiKey: true,
      model: "dall-e-3",
      driver: "openai_compatible",
      baseUrl: "https://api.openai.com/v1",
    },
    video: {
      configured: false,
      hasApiKey: false,
      model: undefined,
      driver: "generic_job",
      baseUrl: "",
    },
  },
  preferences: {
    directMultimodalAnalysisEnabled: true,
  },
  ttsPreferences: {
    resourceId: "seed-tts-2.0",
    speaker: "zh_female_vv_uranus_bigtts",
    modelVariant: "seed-tts-2.0-expressive",
    speechRate: 0,
    loudnessRate: 0,
    emotion: null,
    emotionScale: 4,
    contextTexts: "",
    explicitLanguage: "zh",
    format: "pcm",
    sampleRate: 24000,
    chunkCharLimit: 400,
  },
  analysisRoutePreview: "map_reduce",
};
