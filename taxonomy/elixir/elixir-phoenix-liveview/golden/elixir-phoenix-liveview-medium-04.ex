# golden: function component with attrs, slots, and :global pass-through
defmodule MyAppWeb.CoreComponents.Button do
  use Phoenix.Component

  attr :type, :string, default: "button", values: ~w(button submit reset)
  attr :variant, :string, default: "primary", values: ~w(primary secondary danger)
  attr :disabled, :boolean, default: false
  attr :class, :string, default: nil
  attr :rest, :global, include: ~w(form name value)

  slot :inner_block, required: true

  def button(assigns) do
    ~H"""
    <button
      type={@type}
      disabled={@disabled}
      class={["btn", "btn-#{@variant}", @class]}
      {@rest}
    >
      {render_slot(@inner_block)}
    </button>
    """
  end
end
