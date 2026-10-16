import { ApiClient } from "../services/api";

export const Dashboard = () => {
  const client = new ApiClient();
  return {
    render: () => "Dashboard Content",
    client,
  };
};
