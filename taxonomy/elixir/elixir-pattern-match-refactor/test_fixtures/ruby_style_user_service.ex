# fixture: Ruby/Java-style Elixir service module with defensive nil checks, if/else chains,
# case-on-nil patterns, and maybe_do_* helpers. Models the BoothIQ/te_chris complaint verbatim.
defmodule MyApp.UserService do
  alias MyApp.{Repo, User}

  def fetch_profile(user_id) do
    user = Repo.get(User, user_id)

    if is_nil(user) do
      {:error, :not_found}
    else
      if user.active == true do
        profile = maybe_load_profile(user)

        if is_nil(profile) do
          {:error, :profile_missing}
        else
          {:ok, %{user: user, profile: profile}}
        end
      else
        {:error, :inactive}
      end
    end
  end

  def maybe_load_profile(user) do
    case Repo.get_by(MyApp.Profile, user_id: user.id) do
      nil -> nil
      profile -> profile
    end
  end

  def update_role(user, role) do
    if user != nil && role != nil do
      if role == "admin" do
        User.admin_changeset(user, %{role: role})
      else
        if role == "editor" do
          User.editor_changeset(user, %{role: role})
        else
          if role == "viewer" do
            User.viewer_changeset(user, %{role: role})
          else
            {:error, :invalid_role}
          end
        end
      end
    else
      {:error, :missing_args}
    end
  end

  def display_name(user) do
    name = user && user.name
    if is_nil(name) || name == "" do
      "Anonymous"
    else
      name
    end
  end
end
