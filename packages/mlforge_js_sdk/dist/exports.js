export class ExportsClient {
    constructor(http) {
        this.http = http;
    }
    async list(opts) {
        return this.http.get("/exports", {
            project_id: opts?.project_id,
            limit: opts?.limit ?? 50,
            offset: opts?.offset ?? 0,
        });
    }
    async get(exportId) {
        return this.http.get(`/exports/${exportId}`);
    }
    async start(opts) {
        return this.http.post("/exports", opts);
    }
    async cancel(exportId) {
        return this.http.post(`/exports/${exportId}/cancel`);
    }
    async download(exportId) {
        const response = await fetch(this.http["baseUrl"] + `/exports/${exportId}/download`);
        if (!response.ok) {
            throw new Error(`Export download failed: ${response.statusText}`);
        }
        return response.blob();
    }
}
//# sourceMappingURL=exports.js.map