import type { ModelGatewayStatusResponse } from "@/lib/apiClient";

export const fixtureModelGatewayStatus: ModelGatewayStatusResponse = {
  fixtureMode: true,
  providers: {
    text: {
      configured: true,
      model: "gpt-4o",
      driver: "openai_compatible",
    },
    vision: {
      configured: true,
      model: "gpt-4o",
      driver: "openai_compatible",
    },
    tts: {
      configured: false,
      model: undefined,
      driver: "openai_compatible",
    },
    image: {
      configured: true,
      model: "dall-e-3",
      driver: "openai_compatible",
    },
    video: {
      configured: false,
      model: undefined,
      driver: "generic_job",
    },
  },
};
