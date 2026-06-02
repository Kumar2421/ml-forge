import { describe, it, expect, beforeEach, vi } from "vitest";
import { HttpClient, ApiError } from "../http";

describe("ApiError", () => {
  it("should create error with status and message", () => {
    const error = new ApiError(404, "Not found");
    expect(error.status).toBe(404);
    expect(error.message).toContain("404");
    expect(error.message).toContain("Not found");
  });

  it("should store body payload", () => {
    const body = { detail: "error details" };
    const error = new ApiError(500, "Server error", body);
    expect(error.body).toEqual(body);
  });

  it("should have ApiError name", () => {
    const error = new ApiError(400, "Bad request");
    expect(error.name).toBe("ApiError");
  });
});

describe("HttpClient - 402 Error Handling", () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("should handle 402 with quota details", async () => {
    const mockResponse = new Response(
      JSON.stringify({
        resource: "training_runs",
        used: 5,
        limit: 3,
        upgrade_url: "https://mlforge.in/upgrade",
      }),
      {
        status: 402,
        headers: { "Content-Type": "application/json" },
      }
    );

    global.fetch = vi.fn().mockResolvedValue(mockResponse);
    const client = new HttpClient();

    try {
      await client.get<any>("/some-endpoint");
      expect.fail("Should have thrown ApiError");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const error = e as ApiError;
      expect(error.status).toBe(402);
      expect(error.message).toContain("training_runs");
      expect(error.message).toContain("5/3");
      expect(error.body).toHaveProperty("upgrade_url");
    }
  });

  it("should handle 402 without quota details", async () => {
    const mockResponse = new Response("Payment required", {
      status: 402,
      headers: { "Content-Type": "text/plain" },
    });

    global.fetch = vi.fn().mockResolvedValue(mockResponse);
    const client = new HttpClient();

    try {
      await client.get<any>("/some-endpoint");
      expect.fail("Should have thrown ApiError");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const error = e as ApiError;
      expect(error.status).toBe(402);
      expect(error.message).toContain("Limit exceeded");
    }
  });

  it("should handle other errors unchanged", async () => {
    const mockResponse = new Response("Internal Server Error", {
      status: 500,
      headers: { "Content-Type": "text/plain" },
    });

    global.fetch = vi.fn().mockResolvedValue(mockResponse);
    const client = new HttpClient();

    try {
      await client.get<any>("/some-endpoint");
      expect.fail("Should have thrown ApiError");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const error = e as ApiError;
      expect(error.status).toBe(500);
      expect(error.message).toContain("Internal Server Error");
    }
  });

  it("should handle successful 200 response", async () => {
    const mockResponse = new Response(JSON.stringify({ result: "ok" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

    global.fetch = vi.fn().mockResolvedValue(mockResponse);
    const client = new HttpClient();

    const result = await client.get<any>("/some-endpoint");
    expect(result).toEqual({ result: "ok" });
  });

  it("should handle 204 No Content", async () => {
    const mockResponse = new Response("", {
      status: 204,
      headers: { "Content-Type": "application/json" },
    });

    global.fetch = vi.fn().mockResolvedValue(mockResponse);
    const client = new HttpClient();

    const result = await client.get<any>("/some-endpoint");
    expect(result).toBeUndefined();
  });

  it("should parse JSON error body", async () => {
    const mockResponse = new Response(
      JSON.stringify({ message: "Invalid input" }),
      {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }
    );

    global.fetch = vi.fn().mockResolvedValue(mockResponse);
    const client = new HttpClient();

    try {
      await client.post<any>("/some-endpoint", { invalid: "data" });
      expect.fail("Should have thrown ApiError");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const error = e as ApiError;
      expect(error.body).toHaveProperty("message");
    }
  });

  it("should fallback to text when JSON parsing fails", async () => {
    const mockResponse = new Response("Invalid JSON response", {
      status: 500,
      headers: { "Content-Type": "text/plain" },
    });

    global.fetch = vi.fn().mockResolvedValue(mockResponse);
    const client = new HttpClient();

    try {
      await client.get<any>("/some-endpoint");
      expect.fail("Should have thrown ApiError");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const error = e as ApiError;
      expect(error.body).toBe("Invalid JSON response");
    }
  });

  it("should include Bearer token in request", async () => {
    const mockResponse = new Response(JSON.stringify({}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

    const fetchSpy = vi.fn().mockResolvedValue(mockResponse);
    global.fetch = fetchSpy;

    const client = new HttpClient({ token: "my-token" });
    await client.get<any>("/endpoint");

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer my-token",
        }),
      })
    );
  });
});
