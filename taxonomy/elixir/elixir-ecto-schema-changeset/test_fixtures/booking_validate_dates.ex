# fixture: Booking schema where end_date must be after start_date (custom cross-field validation).
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
    # TODO: add custom validation that end_date > start_date
  end
end
