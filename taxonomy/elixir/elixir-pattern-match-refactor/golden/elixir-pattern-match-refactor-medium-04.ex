defmodule MyApp.RoleRouter do
  def route(%{role: "admin", active: true}), do: :admin_dashboard
  def route(%{role: "admin", active: false}), do: :suspended
  def route(%{role: "editor"}), do: :editor_home
  def route(%{role: "viewer"}), do: :viewer_home
  def route(%{role: "guest"}), do: :landing
  def route(_), do: :unauthorized

  def permission(nil, _resource), do: :denied
  def permission(%{role: "admin"}, _resource), do: :full
  def permission(%{role: "editor", id: uid}, %{owner_id: uid}), do: :write
  def permission(%{role: "editor"}, _resource), do: :read
  def permission(%{role: "viewer"}, _resource), do: :read
  def permission(_user, _resource), do: :denied
end
