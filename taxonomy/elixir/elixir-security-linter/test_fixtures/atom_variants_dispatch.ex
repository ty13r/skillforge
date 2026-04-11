# fixture: atom-exhaustion through less obvious sibling functions
# Vulnerability: List.to_atom, :erlang.binary_to_atom, Module.concat, and
# atom-interpolation sigils. All produce the same class of DoS.
defmodule MyApp.Dispatch do
  def handle_request(req_type, user_id) do
    # List.to_atom variant
    key = List.to_atom(String.to_charlist(req_type))
    dispatch_key(key, user_id)
  end

  def register_worker(name) do
    # :erlang.binary_to_atom variant
    proc_name = :erlang.binary_to_atom(name, :utf8)
    {:ok, _} = GenServer.start_link(MyApp.Worker, [], name: proc_name)
  end

  def build_role_atom(role_str) do
    # atom-interpolation sigil variant
    :"role_#{role_str}"
  end

  def load_module(mod_name) do
    # Module.concat variant — adds a new atom for the concatenated name
    Module.concat([MyApp.Plugins, mod_name])
  end

  defp dispatch_key(_key, _user_id), do: :ok
end
