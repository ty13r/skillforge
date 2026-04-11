# fixture: shared Tag schema — referenced by many_to_many challenges
defmodule MyApp.Blog.Tag do
  use Ecto.Schema
  import Ecto.Changeset

  schema "tags" do
    field :name, :string
    field :slug, :string

    many_to_many :posts, MyApp.Blog.Post, join_through: "posts_tags"

    timestamps(type: :utc_datetime)
  end

  def changeset(tag, attrs) do
    tag
    |> cast(attrs, [:name, :slug])
    |> validate_required([:name, :slug])
    |> unique_constraint(:slug)
  end
end
