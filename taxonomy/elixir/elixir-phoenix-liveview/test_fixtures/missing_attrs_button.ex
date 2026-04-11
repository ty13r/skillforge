# fixture: function component without attr/slot declarations — receives everything undocumented
defmodule MyAppWeb.CoreComponents.ButtonMissingAttrs do
  use Phoenix.Component

  # ANTI-PATTERN: no attr declarations, no slot declaration for inner_block,
  # so the component accepts anything and compiler cannot warn on unknown attrs.
  def button(assigns) do
    ~H"""
    <button
      type={@type || "button"}
      class={"btn btn-#{@variant} #{@class}"}
      disabled={@disabled}
    >
      {render_slot(@inner_block)}
    </button>
    """
  end
end
