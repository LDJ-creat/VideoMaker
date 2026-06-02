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
};
