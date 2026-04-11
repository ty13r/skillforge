# fixture: empty scaffold Claude must fill in from scratch based on a prompt.
# Used by "design a schema from domain description" challenges.
defmodule MyApp.Scaffold.User do
  use Ecto.Schema

  # TODO: fill in based on prompt requirements
  schema "users" do
    timestamps(type: :utc_datetime)
  end
end
