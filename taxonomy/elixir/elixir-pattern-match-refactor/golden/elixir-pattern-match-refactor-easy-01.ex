defmodule MyApp.UserService do
  alias MyApp.{Repo, User}

  def display_name(%User{name: name}) when is_binary(name) and name != "", do: name
  def display_name(_user), do: "Anonymous"
end
