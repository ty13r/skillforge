# fixture: cond-heavy routing logic with truthiness checks. Multi-clause function heads
# with guards are the idiomatic refactor target.
defmodule MyApp.RoleRouter do
  def route(user) do
    cond do
      user.role == "admin" and user.active ->
        :admin_dashboard

      user.role == "admin" and not user.active ->
        :suspended

      user.role == "editor" ->
        :editor_home

      user.role == "viewer" ->
        :viewer_home

      user.role == "guest" ->
        :landing

      true ->
        :unauthorized
    end
  end

  def permission(user, resource) do
    cond do
      is_nil(user) ->
        :denied

      user.role == "admin" ->
        :full

      user.role == "editor" and resource.owner_id == user.id ->
        :write

      user.role == "editor" ->
        :read

      user.role == "viewer" ->
        :read

      true ->
        :denied
    end
  end
end
