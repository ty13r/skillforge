# golden: Ecto.Enum instead of stringly-typed status with validate_inclusion
defmodule MyApp.Tasks.Task do
  use Ecto.Schema
  import Ecto.Changeset

  schema "tasks" do
    field :title, :string
    field :status, Ecto.Enum, values: [:pending, :in_progress, :done, :cancelled]
    field :priority, Ecto.Enum, values: [:low, :medium, :high]

    timestamps(type: :utc_datetime)
  end

  def changeset(task, attrs) do
    task
    |> cast(attrs, [:title, :status, :priority])
    |> validate_required([:title, :status])
  end
end
