# golden: fix naive_datetime timestamps to utc_datetime
defmodule MyApp.Logging.LogEntry do
  use Ecto.Schema
  import Ecto.Changeset

  schema "log_entries" do
    field :message, :string
    field :level, :string
    field :source_system, :string

    timestamps(type: :utc_datetime)
  end

  def changeset(entry, attrs) do
    entry
    |> cast(attrs, [:message, :level, :source_system])
    |> validate_required([:message, :level])
  end
end
