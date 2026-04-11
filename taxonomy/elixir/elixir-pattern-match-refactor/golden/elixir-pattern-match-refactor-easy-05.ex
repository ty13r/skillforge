defmodule MyApp.UserService do
  def update_role(_user, role) when role not in ["admin", "editor", "viewer"],
    do: {:error, :invalid_role}

  def update_role(nil, _role), do: {:error, :missing_args}
  def update_role(user, "admin"), do: MyApp.User.admin_changeset(user, %{role: "admin"})
  def update_role(user, "editor"), do: MyApp.User.editor_changeset(user, %{role: "editor"})
  def update_role(user, "viewer"), do: MyApp.User.viewer_changeset(user, %{role: "viewer"})
end
