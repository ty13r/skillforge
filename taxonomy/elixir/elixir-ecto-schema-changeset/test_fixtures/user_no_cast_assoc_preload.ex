# fixture: cast_assoc called without preloading associations.
# Runtime error: "Please preload your associations before manipulating them through changesets."
defmodule MyApp.Blog.UserWithPosts do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :name, :string
    has_many :posts, MyApp.Blog.Post

    timestamps(type: :utc_datetime)
  end

  # PROBLEM: this crashes at runtime if user.posts isn't preloaded.
  def changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :name])
    |> validate_required([:email, :name])
    |> cast_assoc(:posts)
  end
end
