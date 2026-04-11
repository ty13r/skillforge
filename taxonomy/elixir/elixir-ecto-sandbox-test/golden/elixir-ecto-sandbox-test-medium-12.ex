# Golden: LiveView on_mount sandbox hook using Phoenix.Ecto.SQL.Sandbox.allow/2
defmodule MyAppWeb.UserAuth do
  import Phoenix.LiveView
  import Phoenix.Component

  def on_mount(:sandbox, _params, _session, socket) do
    allow_sandbox(socket)
    {:cont, socket}
  end

  def on_mount(:mount_current_user, _params, session, socket) do
    {:cont, assign_new(socket, :current_user, fn ->
      if user_token = session["user_token"], do: lookup_user(user_token)
    end)}
  end

  defp allow_sandbox(socket) do
    case get_connect_info(socket, :user_agent) do
      nil ->
        :ok

      user_agent ->
        metadata = Phoenix.Ecto.SQL.Sandbox.decode_metadata(user_agent)
        Phoenix.Ecto.SQL.Sandbox.allow(metadata, Ecto.Adapters.SQL.Sandbox)
    end
  end

  defp lookup_user(_token), do: nil
end
