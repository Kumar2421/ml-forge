/**
 * @mlforge/sdk — JavaScript/TypeScript SDK for MLForge Studio
 *
 * Requires MLForge Studio desktop app running locally (default: http://127.0.0.1:8005)
 * Install desktop app: npm install -g mlforge-studio
 *
 * @example
 * import { MLForge } from "@mlforge/sdk";
 * const forge = new MLForge();
 * const models = await forge.models.list();
 */
export { MLForge, default } from "./mlforge.js";
export { ModelsClient } from "./models.js";
export { TrainingClient } from "./training.js";
export { InferenceClient } from "./inference.js";
export { DatasetsClient } from "./datasets.js";
export { BenchmarkClient } from "./benchmark.js";
export { ProjectsClient } from "./projects.js";
export { ExportsClient } from "./exports.js";
export { AuthClient } from "./auth.js";
export type { MLForgeOptions, ApiError, } from "./http.js";
export type { AuthOptions } from "./auth.js";
export type { Model, ModelJob } from "./models.js";
export type { TrainRun, TrainStartOptions } from "./training.js";
export type { InferenceResult, InferenceOptions } from "./inference.js";
export type { Dataset, DatasetJob, DatasetAnalytics, ImportOptions } from "./datasets.js";
export type { BenchmarkResult, BenchmarkJob, BenchmarkRunOptions } from "./benchmark.js";
export type { Project, ProjectCreateOptions } from "./projects.js";
export type { ExportJob, ExportOptions } from "./exports.js";
//# sourceMappingURL=index.d.ts.map