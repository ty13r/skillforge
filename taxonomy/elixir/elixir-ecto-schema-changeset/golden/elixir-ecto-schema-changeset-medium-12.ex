# golden: booking with custom cross-field validation (end_date > start_date)
defmodule MyApp.Bookings.Booking do
  use Ecto.Schema
  import Ecto.Changeset

  schema "bookings" do
    field :guest_name, :string
    field :start_date, :date
    field :end_date, :date
    field :room_id, :integer

    timestamps(type: :utc_datetime)
  end

  def changeset(booking, attrs) do
    booking
    |> cast(attrs, [:guest_name, :start_date, :end_date, :room_id])
    |> validate_required([:guest_name, :start_date, :end_date, :room_id])
    |> validate_end_after_start()
  end

  defp validate_end_after_start(changeset) do
    start_date = get_field(changeset, :start_date)
    end_date = get_field(changeset, :end_date)

    cond do
      is_nil(start_date) or is_nil(end_date) ->
        changeset

      Date.compare(end_date, start_date) in [:gt, :eq] ->
        changeset

      true ->
        add_error(changeset, :end_date, "must be after start date")
    end
  end
end
