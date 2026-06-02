export class InferenceClient {
    constructor(http) {
        this.http = http;
    }
    async run(opts) {
        return this.http.post("/inference/run", opts);
    }
    async getSchema(task) {
        return this.http.get("/inference/schema", { task });
    }
}
//# sourceMappingURL=inference.js.map