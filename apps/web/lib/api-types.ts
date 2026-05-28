export type DataSource = "api" | "fixture";

export type ApiMeta = {
  dataSource: DataSource;
};

export type ApiResult<T> = {
  data: T;
  meta: ApiMeta;
};

export const DATA_SOURCE_HEADER = "X-Videomaker-Data-Source";

export function metaFromResponse(response: Response): ApiMeta {
  const header = response.headers.get(DATA_SOURCE_HEADER);
  return { dataSource: header === "fixture" ? "fixture" : "api" };
}
