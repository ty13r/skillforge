# fixture: Inconsistent refactoring philosophy — some functions use function heads,
# others do case-in-body with no defensible reason. Drives the refactor-philosophy
# foundation challenges (consistency + when-NOT-to-refactor).
defmodule MyApp.PermissionService do
  def can?(user, :admin_panel) do
    case user.role do
      "admin" -> true
      "superadmin" -> true
      _ -> false
    end
  end

  def can?(%{role: "viewer"}, :edit), do: false
  def can?(%{role: "viewer"}, :view), do: true
  def can?(%{role: "editor"}, :edit), do: true
  def can?(%{role: "editor"}, :view), do: true

  def can?(user, action) do
    if user.role == "admin" do
      true
    else
      if action == :delete do
        false
      else
        user.permissions[action] == true
      end
    end
  end

  def describe(%{role: role, name: name}) when is_binary(name) do
    "#{name} (#{role})"
  end

  def describe(user) do
    case user do
      %{name: nil} -> "Anonymous"
      %{name: name} -> name
      _ -> "Unknown"
    end
  end
end
