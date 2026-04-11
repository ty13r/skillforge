defmodule MyApp.UserService do
  alias MyApp.{Repo, User, Profile}

  def fetch_profile(user_id) do
    with %User{active: true} = user <- Repo.get(User, user_id) || {:error, :not_found},
         %Profile{} = profile <- load_profile(user) || {:error, :profile_missing} do
      {:ok, %{user: user, profile: profile}}
    else
      %User{active: false} -> {:error, :inactive}
      {:error, _reason} = err -> err
    end
  end

  defp load_profile(%User{id: id}), do: Repo.get_by(Profile, user_id: id)
end
