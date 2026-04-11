# golden: atom-variants fix — replace List.to_atom, binary_to_atom, atom interpolation
defmodule MyApp.Dispatch do
  @allowed_types %{
    "create" => :create,
    "update" => :update,
    "delete" => :delete
  }

  def handle_request(req_type, user_id) do
    key = Map.get(@allowed_types, req_type, :unknown)
    dispatch_key(key, user_id)
  end

  def register_worker(name) do
    # Use Registry with string keys instead of dynamically-minted atoms
    {:ok, _} =
      GenServer.start_link(MyApp.Worker, [],
        name: {:via, Registry, {MyApp.WorkerRegistry, name}}
      )
  end

  def build_role_atom(role_str) do
    case role_str do
      "admin" -> :admin
      "moderator" -> :moderator
      _ -> :user
    end
  end

  def load_module(_mod_name) do
    # Explicit allowlist — never Module.concat user input
    MyApp.Plugins.DefaultPlugin
  end

  defp dispatch_key(_key, _user_id), do: :ok
end
