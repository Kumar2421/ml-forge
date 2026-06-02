import type { HttpClient } from "./http.js";
export interface Detection {
    class_name: string;
    class_id: number;
    confidence: number;
    bbox: [number, number, number, number];
}
export interface InferenceResult {
    task: string;
    model_id: string;
    latency_ms: number;
    detections?: Detection[];
    classification?: {
        class_name: string;
        confidence: number;
    }[];
    text?: string;
}
export interface InferenceOptions {
    model_id: string;
    task: string;
    image_path?: string;
    image_base64?: string;
    text_input?: string;
    conf_threshold?: number;
    iou_threshold?: number;
    imgsz?: number;
    device?: string;
}
export declare class InferenceClient {
    private http;
    constructor(http: HttpClient);
    run(opts: InferenceOptions): Promise<InferenceResult>;
    getSchema(task: string): Promise<unknown>;
}
//# sourceMappingURL=inference.d.ts.map