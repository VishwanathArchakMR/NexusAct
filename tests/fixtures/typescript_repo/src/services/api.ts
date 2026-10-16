export class ApiClient {
  public baseUrl: string = "https://api.lifeassist.test";

  public async fetchStatus(): Promise<{ status: string }> {
    return { status: "ok" };
  }
}
