import { ApiClient } from "./api";

export class AuthService {
  private client: ApiClient;

  constructor(client?: ApiClient) {
    this.client = client || new ApiClient();
  }

  public async login(token: string): Promise<boolean> {
    const res = await this.client.fetchStatus();
    return res.status === "ok" && Boolean(token);
  }
}
