local function extract_anchor(block)
  if block.t ~= "RawBlock" or block.format ~= "html" then
    return nil
  end

  return block.text:match("^%s*<a%s+id=[\"']([^\"']+)[\"']%s*></a>%s*$")
end

local function extract_inline_anchor(inline)
  if inline.t ~= "RawInline" or inline.format ~= "html" then
    return nil
  end

  return inline.text:match("^%s*<a%s+id=[\"']([^\"']+)[\"']%s*>%s*$")
end

local function extract_anchor_paragraph(block)
  if block.t ~= "Para" then
    return nil
  end

  local content = block.content
  if #content < 2 then
    return nil
  end

  local anchor = extract_inline_anchor(content[1])
  local closing = content[2]
  if not anchor
      or closing.t ~= "RawInline"
      or closing.format ~= "html"
      or not closing.text:match("^%s*</a>%s*$") then
    return nil
  end

  if #content == 2 then
    return anchor, nil, nil
  end

  if #content < 6
      or content[3].t ~= "SoftBreak"
      or content[4].t ~= "Str"
      or not content[4].text:match("^#+$")
      or content[5].t ~= "Space" then
    return nil
  end

  local heading = {}
  for index = 6, #content do
    table.insert(heading, content[index])
  end
  return anchor, #content[4].text, heading
end

local convert_code

function Link(link)
  local target = link.target
  target = target:gsub("BEGINNER_GUIDE_ZH%.md", "BEGINNER_GUIDE_ZH.pdf")
  target = target:gsub("API_REFERENCE_ZH%.md", "API_REFERENCE_ZH.pdf")
  link.target = target
  local content = pandoc.walk_block(
    pandoc.Para(link.content),
    {Code = convert_code}
  )
  link.content = content.content
  return link
end

local function escape_latex_code(value)
  value = value:gsub("\\", "\\textbackslash{}")
  value = value:gsub("([%%#$&_{}])", "\\%1")
  value = value:gsub("([:_/%.%-])", "%1\\allowbreak{}")
  value = value:gsub("([a-z0-9])([A-Z])", "%1\\allowbreak{}%2")
  return value
end

convert_code = function(code)
  -- Long inline C++ names otherwise become an unbreakable lstinline box.
  if #code.text < 10 then
    return code
  end
  return pandoc.RawInline(
    "latex",
    "\\texttt{" .. escape_latex_code(code.text) .. "}"
  )
end

function Code(code)
  return convert_code(code)
end

local function wrap_code_text(text)
  local wrapped = {}
  for line in (text .. "\n"):gmatch("(.-)\n") do
    while #line > 78 do
      local prefix = line:sub(1, 78)
      local split = prefix:match("^.*()%s+")
      local comma = prefix:match("^.*(),%s*")
      if comma and (not split or comma > split) then
        split = comma
      end
      if not split or split < 32 then
        split = 72
      end
      wrapped[#wrapped + 1] = line:sub(1, split):gsub("%s+$", "")
      line = "    " .. line:sub(split + 1):gsub("^%s+", "")
    end
    wrapped[#wrapped + 1] = line
  end
  return table.concat(wrapped, "\n")
end

function CodeBlock(block)
  block.text = wrap_code_text(block.text)
  return block
end

function Table(table_element)
  local width_sets = {
    [2] = {0.35, 0.65},
    [3] = {0.18, 0.20, 0.62},
    [4] = {0.18, 0.24, 0.18, 0.40},
    [5] = {0.14, 0.18, 0.14, 0.18, 0.36},
  }
  local widths = width_sets[#table_element.colspecs]
  if not widths then
    widths = {}
    for index = 1, #table_element.colspecs do
      widths[index] = 1 / #table_element.colspecs
    end
  end

  for index, column_spec in ipairs(table_element.colspecs) do
    table_element.colspecs[index] = {column_spec[1], widths[index]}
  end
  return table_element
end

function Pandoc(document)
  local blocks = {}
  local pending_anchor = nil
  local skipped_document_title = false
  local skipping_manual_toc = false

  for _, block in ipairs(document.blocks) do
    if skipping_manual_toc then
      if block.t == "Header" and block.level <= 2 then
        skipping_manual_toc = false
      else
        goto continue
      end
    end

    local anchor, level, heading = extract_anchor_paragraph(block)
    if anchor and level then
      local heading_text = pandoc.utils.stringify(heading)
      if level == 1 and not skipped_document_title then
        skipped_document_title = true
        pending_anchor = nil
      elseif level == 2 and heading_text == "目录" then
        skipping_manual_toc = true
        pending_anchor = nil
      else
        table.insert(
          blocks,
          pandoc.Header(level, heading, pandoc.Attr(anchor, {}, {}))
        )
      end
      pending_anchor = nil
    elseif anchor then
      pending_anchor = anchor
    else
      local block_anchor = extract_anchor(block)
      if block_anchor then
        pending_anchor = block_anchor
      else
        local header_text = block.t == "Header"
            and pandoc.utils.stringify(block.content)
            or ""
        if block.t == "Header" and block.level == 1 and not skipped_document_title then
          skipped_document_title = true
          pending_anchor = nil
          goto continue
        end
        if block.t == "Header" and block.level == 2 and header_text == "目录" then
          skipping_manual_toc = true
          pending_anchor = nil
          goto continue
        end
        if pending_anchor and block.t == "Header" then
          block.identifier = pending_anchor
        end
        pending_anchor = nil
        table.insert(blocks, block)
      end
    end
    ::continue::
  end

  return pandoc.Pandoc(blocks, document.meta)
end
