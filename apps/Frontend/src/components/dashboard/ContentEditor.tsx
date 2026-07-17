"use client";

import React, { useMemo, useState, useEffect, useRef } from 'react';
import { Image as ImageIcon, SmilePlus, MessageSquare, Pencil, MoreHorizontal, Copy, Trash2, Download, CopyPlus, Bold, Italic, Underline, Palette, Highlighter, GripVertical } from 'lucide-react';
import { PageItem } from '@/app/dashboard/DashboardContent';
import { useEditor, EditorContent, ReactNodeViewRenderer, NodeViewWrapper } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';
import StarterKit from '@tiptap/starter-kit';
import { Underline as UnderlineExtension } from '@tiptap/extension-underline';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import { Highlight } from '@tiptap/extension-highlight';
import { Placeholder } from '@tiptap/extension-placeholder';
import { Extension, Node as TiptapNode, mergeAttributes } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import { DragHandle } from '@tiptap/extension-drag-handle-react';
const DragHandleComponent = DragHandle as any;
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import { MathExtension } from '@aarkue/tiptap-math-extension';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { Type, Heading1, Heading2, Heading3, List, ListOrdered, CheckSquare, ChevronRight, FilePlus, Quote, Minus, FileText, Table as TableIcon } from 'lucide-react';

const Summary = TiptapNode.create({
  name: 'summary',
  content: 'inline*',
  group: 'summary',
  parseHTML() {
    return [{ tag: 'summary' }];
  },
  renderHTML({ HTMLAttributes }) {
    return ['summary', mergeAttributes(HTMLAttributes), 0];
  },
});

const Details = TiptapNode.create({
  name: 'details',
  group: 'block',
  content: 'summary block+',
  parseHTML() {
    return [{ tag: 'details' }];
  },
  renderHTML({ HTMLAttributes }) {
    return ['details', mergeAttributes(HTMLAttributes), 0];
  },
});

const PageLinkComponent = (props: any) => {
  const pageId = props.node.attrs.pageId;
  const editor = props.editor;
  
  const allPages = editor.storage.pageLink?.allPages || [];
  const onSelectPage = editor.storage.pageLink?.onSelectPage;
  
  const page = allPages.find((p: any) => p.id === pageId);
  
  return (
    <NodeViewWrapper className="page-link-wrapper" contentEditable={false}>
      <div 
        className="flex items-center gap-2.5 cursor-pointer hover:bg-white/5 p-2 rounded-md transition-colors w-max pr-6 group border border-[#666565]/30 my-2 bg-[#0f0f13]/50"
        onClick={() => {
           if (onSelectPage && pageId) {
             onSelectPage(pageId);
           }
        }}
      >
        <span className="flex items-center justify-center shrink-0 pointer-events-none select-none">
          {page?.icon ? (
            <span className="text-[20px]">{page.icon}</span>
          ) : (
            <FileText className="w-5 h-5 text-neutral-400" />
          )}
        </span>
        <span className="text-[16px] text-[#d1d5db] font-medium border-b border-[#d1d5db]/40 group-hover:border-[#d1d5db] transition-colors truncate max-w-[200px] pointer-events-none select-none">
          {page?.title || 'Untitled'}
        </span>
      </div>
    </NodeViewWrapper>
  );
};

const PageLinkExtension = TiptapNode.create({
  name: 'pageLink',
  group: 'block',
  atom: true,
  
  addAttributes() {
    return {
      pageId: { 
        default: null,
        parseHTML: element => element.getAttribute('pageid') || element.getAttribute('data-page-id'),
        renderHTML: attributes => {
          if (!attributes.pageId) return {};
          return { 'pageid': attributes.pageId, 'data-page-id': attributes.pageId };
        }
      },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-type="page-link"]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes, { 'data-type': 'page-link' })];
  },

  addNodeView() {
    return ReactNodeViewRenderer(PageLinkComponent);
  },
  
  addStorage() {
    return {
      allPages: [],
      onSelectPage: null,
    };
  }
});

const BlockSelection = Extension.create({
  name: 'blockSelection',
  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('blockSelection'),
        props: {
          decorations(state) {
            const { selection, doc } = state;
            const decorations: Decoration[] = [];
            
            if (!selection.empty && selection.from !== selection.to) {
              let blockCount = 0;
              doc.nodesBetween(selection.from, selection.to, (node) => {
                if (node.isBlock) blockCount++;
              });
              
              if (blockCount > 1) {
                doc.nodesBetween(selection.from, selection.to, (node, pos) => {
                  if (node.isBlock) {
                    decorations.push(
                      Decoration.node(pos, pos + node.nodeSize, {
                        class: 'multi-selected-block',
                      })
                    );
                  }
                });
              }
            }
            return DecorationSet.create(doc, decorations);
          },
        },
      }),
    ];
  },
});

type ContentEditorProps = {
  activePage?: PageItem;
  allPages?: PageItem[];
  updatePage?: (id: string, updates: Partial<PageItem>) => void;
  onSelectPage?: (id: string) => void;
  onDuplicatePage?: (id: string) => void;
  onDeletePage?: (id: string) => void;
  onAddPage?: (parentId: string | null, preventSwitch?: boolean) => string | void;
};

const colors = [
  { name: 'Default', value: 'inherit' },
  { name: 'Gray', value: '#9ca3af' },
  { name: 'Brown', value: '#d97706' },
  { name: 'Orange', value: '#ea580c' },
  { name: 'Yellow', value: '#ca8a04' },
  { name: 'Green', value: '#16a34a' },
  { name: 'Blue', value: '#2563eb' },
  { name: 'Purple', value: '#9333ea' },
  { name: 'Pink', value: '#db2777' },
  { name: 'Red', value: '#dc2626' },
];

const highlights = [
  { name: 'None', value: 'transparent' },
  { name: 'Gray', value: 'rgba(156, 163, 175, 0.3)' },
  { name: 'Brown', value: 'rgba(217, 119, 6, 0.3)' },
  { name: 'Orange', value: 'rgba(234, 88, 12, 0.3)' },
  { name: 'Yellow', value: 'rgba(202, 138, 4, 0.3)' },
  { name: 'Green', value: 'rgba(22, 163, 74, 0.3)' },
  { name: 'Blue', value: 'rgba(37, 99, 235, 0.3)' },
  { name: 'Purple', value: 'rgba(147, 51, 234, 0.3)' },
  { name: 'Pink', value: 'rgba(219, 39, 119, 0.3)' },
  { name: 'Red', value: 'rgba(220, 38, 38, 0.3)' },
];

const ContentEditor = ({ activePage, allPages = [], updatePage, onSelectPage, onDuplicatePage, onDeletePage, onAddPage }: ContentEditorProps) => {
  const [isIconPickerOpen, setIsIconPickerOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [showTextColor, setShowTextColor] = useState(false);
  const [showHighlightColor, setShowHighlightColor] = useState(false);

  const [slashQuery, setSlashQuery] = useState<string | null>(null);
  const [slashCoords, setSlashCoords] = useState<{ top: number; left: number } | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const emojis = ['📝', '📚', '🚀', '💡', '🧠', '💻', '☁️', '🔥', '⭐', '🎯', '✏️', '📌', '📁', '📊', '🌐', '🛠️', '✅', '✨', '🏆', '🎉', '🎧', '🎨', '🧩', '⚡'];

  const breadcrumbs = useMemo(() => {
    if (!activePage) return [];
    const path = [];
    let currentId = activePage.parentId;
    while (currentId) {
      const parent = allPages.find(p => p.id === currentId);
      if (parent) {
        path.unshift({ id: parent.id, title: parent.title || 'Untitled' });
        currentId = parent.parentId;
      } else {
        break;
      }
    }
    return path;
  }, [activePage, allPages]);

  const subPages = useMemo(() => {
    if (!activePage) return [];
    return allPages.filter(p => p.parentId === activePage.id);
  }, [activePage, allPages]);

  const stateRef = useRef({ activePage, allPages, updatePage, onDeletePage });
  useEffect(() => {
    stateRef.current = { activePage, allPages, updatePage, onDeletePage };
  }, [activePage, allPages, updatePage, onDeletePage]);

  const editor = useEditor({
    extensions: [
      StarterKit,
      UnderlineExtension,
      TextStyle,
      Color,
      Highlight.configure({ multicolor: true }),
      Details,
      Summary,
      BlockSelection,
      PageLinkExtension,
      Placeholder.configure({
        placeholder: "Press '/' for commands...",
      }),
      TaskList,
      TaskItem.configure({
        nested: true,
      }),
      MathExtension.configure({ evaluation: false }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: activePage?.content || '',
    onUpdate: ({ editor }) => {
      const { activePage, allPages, updatePage, onDeletePage } = stateRef.current;
      if (activePage) {
        updatePage?.(activePage.id, { content: editor.getHTML() });

        // Check if any child pages were deleted from the editor
        // Only run deletion logic if the editor is focused (user actively editing).
        // This prevents programmatic content loading (like switching pages) from accidentally deleting pages!
        if (editor.isFocused) {
          const currentSubpageIds = new Set<string>();
          editor.state.doc.descendants((node) => {
            if (node.type.name === 'pageLink' && node.attrs.pageId) {
              currentSubpageIds.add(node.attrs.pageId);
            }
          });

          const childPages = allPages.filter(p => p.parentId === activePage.id);
          childPages.forEach(child => {
            if (!currentSubpageIds.has(child.id)) {
              onDeletePage?.(child.id);
            }
          });
        }
      }
    },
    editorProps: {
      attributes: {
        class: 'w-full min-h-[500px] text-[19px] text-white outline-none leading-relaxed font-light tiptap-editor',
      },
      handleKeyDown: (view, event) => {
        if (slashQueryRef.current !== null) {
          const items = filteredItemsRef.current;
          const index = selectedIndexRef.current;

          if (event.key === 'ArrowDown') {
            setSelectedIndex((index + 1) % items.length);
            return true;
          }
          if (event.key === 'ArrowUp') {
            setSelectedIndex((index - 1 + items.length) % items.length);
            return true;
          }
          if (event.key === 'Enter') {
            if (items[index]) {
              executeCommandRef.current?.(items[index]);
              return true;
            }
          }
          if (event.key === 'Escape') {
            setSlashQuery(null);
            return true;
          }
        }
        return false;
      }
    },
  });

  const menuItems = useMemo(() => [
    {
      id: 'text',
      title: 'Text',
      description: 'Start writing with plain text.',
      icon: <Type className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().setParagraph().run(),
    },
    {
      id: 'h1',
      title: 'Heading 1',
      description: 'Big section heading.',
      icon: <Heading1 className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().toggleHeading({ level: 1 }).run(),
    },
    {
      id: 'h2',
      title: 'Heading 2',
      description: 'Medium section heading.',
      icon: <Heading2 className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().toggleHeading({ level: 2 }).run(),
    },
    {
      id: 'h3',
      title: 'Heading 3',
      description: 'Small section heading.',
      icon: <Heading3 className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().toggleHeading({ level: 3 }).run(),
    },
    {
      id: 'bulletList',
      title: 'Bulleted list',
      description: 'Create a simple bulleted list.',
      icon: <List className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().toggleBulletList().run(),
    },
    {
      id: 'orderedList',
      title: 'Numbered list',
      description: 'Create a list with numbering.',
      icon: <ListOrdered className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().toggleOrderedList().run(),
    },
    {
      id: 'todoList',
      title: 'To-do list',
      description: 'Track tasks with a to-do list.',
      icon: <CheckSquare className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().toggleTaskList().run(),
    },
    {
      id: 'page',
      title: 'Page',
      description: 'Create a nested sub-page.',
      icon: <FilePlus className="w-4 h-4 text-neutral-400" />,
      action: () => {
        if (activePage) {
          const newPageId = onAddPage?.(activePage.id, true);
          if (newPageId) {
            editor?.chain().focus().insertContent({
              type: 'pageLink',
              attrs: { pageId: newPageId }
            }).run();
          }
        }
      },
    },
    {
      id: 'quote',
      title: 'Quote',
      description: 'Capture a quote.',
      icon: <Quote className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().toggleBlockquote().run(),
    },
    {
      id: 'divider',
      title: 'Divider',
      description: 'Visually divide sections with a line.',
      icon: <Minus className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().setHorizontalRule().run(),
    },
    {
      id: 'table',
      title: 'Table',
      description: 'Insert a 3x3 grid table.',
      icon: <TableIcon className="w-4 h-4 text-neutral-400" />,
      action: () => editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(),
    },
  ], [editor, activePage, onAddPage]);

  useEffect(() => {
    if (editor) {
      (editor.storage as any).pageLink.allPages = allPages;
      (editor.storage as any).pageLink.onSelectPage = onSelectPage;
    }
  }, [editor, allPages, onSelectPage]);

  const filteredItems = useMemo(() => {
    if (slashQuery === null) return [];
    const q = slashQuery.toLowerCase();
    return menuItems.filter(item => 
      item.title.toLowerCase().includes(q) || 
      item.description.toLowerCase().includes(q)
    );
  }, [slashQuery, menuItems]);

  useEffect(() => {
    if (slashQuery !== null) {
      const el = document.getElementById(`slash-item-${selectedIndex}`);
      if (el) {
        el.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex, slashQuery]);

  const slashQueryRef = useRef<string | null>(null);
  const selectedIndexRef = useRef(0);
  const filteredItemsRef = useRef<any[]>([]);
  const executeCommandRef = useRef<((item: any) => void) | null>(null);

  useEffect(() => {
    slashQueryRef.current = slashQuery;
  }, [slashQuery]);

  useEffect(() => {
    selectedIndexRef.current = selectedIndex;
  }, [selectedIndex]);

  useEffect(() => {
    filteredItemsRef.current = filteredItems;
  }, [filteredItems]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [slashQuery]);

  const executeCommand = (item: any) => {
    if (!editor || !activePage) return;

    const { state } = editor;
    const { selection } = state;
    const { $from } = selection;

    const text = $from.parent.textBetween(0, $from.parentOffset, null, ' ');
    const match = text.match(/(?:^|\s)\/([a-zA-Z0-9]*)$/);

    if (match) {
      const startPos = selection.from - (match[1].length + 1);
      editor.chain().focus().deleteRange({ from: startPos, to: selection.from }).run();
    }

    item.action();
    setSlashQuery(null);
    setSlashCoords(null);
  };

  useEffect(() => {
    executeCommandRef.current = executeCommand;
  }, [editor, activePage, executeCommand]);

  const lastPageIdRef = useRef(activePage?.id);
  
  useEffect(() => {
    if (editor && activePage) {
      const isSamePage = lastPageIdRef.current === activePage.id;
      lastPageIdRef.current = activePage.id;
      
      const currentContent = activePage.content || '';
      if (!isSamePage || (editor.getHTML() !== currentContent && !editor.isFocused)) {
        setTimeout(() => {
          editor.commands.setContent(currentContent);
        }, 0);
      }
    }
  }, [activePage?.id, activePage?.content, editor]);

  // Sync cursor selection position for suggestion popup coords
  useEffect(() => {
    if (!editor) return;

    const handleUpdate = () => {
      const { state, view } = editor;
      const { selection } = state;
      const { $from } = selection;

      if (!$from.parent.isTextblock) {
        setSlashQuery(null);
        return;
      }

      const text = $from.parent.textBetween(0, $from.parentOffset, null, ' ');
      const match = text.match(/(?:^|\s)\/([a-zA-Z0-9]*)$/);

      if (match) {
        const query = match[1];
        setSlashQuery(query);

        try {
          const domPos = view.coordsAtPos(selection.from);
          const scrollContainer = view.dom.closest('main') || view.dom.parentElement!;
          const containerRect = scrollContainer.getBoundingClientRect();
          setSlashCoords({
            top: domPos.top - containerRect.top + scrollContainer.scrollTop + 28,
            left: domPos.left - containerRect.left + scrollContainer.scrollLeft,
          });
        } catch (e) {
          // coordinate lookup fallback
        }
      } else {
        setSlashQuery(null);
        setSlashCoords(null);
      }
    };

    editor.on('selectionUpdate', handleUpdate);
    editor.on('update', handleUpdate);

    return () => {
      editor.off('selectionUpdate', handleUpdate);
      editor.off('update', handleUpdate);
    };
  }, [editor]);

  // Close color menu on selection change
  useEffect(() => {
    if (!editor) return;
    const hideDropdowns = () => {
      setShowTextColor(false);
      setShowHighlightColor(false);
    };
    editor.on('selectionUpdate', hideDropdowns);
    return () => {
      editor.off('selectionUpdate', hideDropdowns);
    };
  }, [editor]);

  const handleExport = () => {
    if (!activePage) return;
    const element = document.createElement("a");
    const content = editor ? editor.getText() : (activePage.content || '').replace(/<[^>]+>/g, '');
    const file = new Blob([activePage.title + "\n\n" + content], {type: 'text/plain'});
    element.href = URL.createObjectURL(file);
    element.download = `${activePage.title || 'Untitled'}.txt`;
    document.body.appendChild(element); 
    element.click();
    setIsMenuOpen(false);
  };

  const handleCopy = () => {
    if (!activePage) return;
    const content = editor ? editor.getText() : (activePage.content || '').replace(/<[^>]+>/g, '');
    navigator.clipboard.writeText(content);
    setIsMenuOpen(false);
  };

  if (!activePage) {
    return (
      <main className="flex-1 h-[calc(100vh-40px)] text-white my-[20px] border border-[#666565]/80 rounded-lg mr-[20px] flex items-center justify-center">
        <p className="text-gray-500">No page selected</p>
      </main>
    );
  }

  return (
    <main className="flex-1 h-[calc(100vh-40px)] overflow-y-auto custom-scrollbar text-white my-[20px] border border-[#666565]/50 rounded-lg px-[45px] py-[35px] mx-[20px] relative">
      
      {/* Breadcrumb Header */}
      <div className="absolute top-[25px] left-[45px] right-[45px] flex items-center justify-between z-10">
        <div className="text-[14px] text-[#6b7280] font-light flex items-center gap-1.5">
          {breadcrumbs.length > 0 ? (
            <>
              <span>..</span>
              <span>/</span>
              {breadcrumbs.map((bc, i) => (
                <React.Fragment key={i}>
                  <span 
                    className="truncate max-w-[100px] cursor-pointer hover:text-white hover:underline underline-offset-4 transition-colors"
                    onClick={() => onSelectPage?.(bc.id)}
                  >
                    {bc.title}
                  </span>
                  <span>/</span>
                </React.Fragment>
              ))}
              <span className="text-[#9ca3af]">{activePage.title || 'Untitled'}</span>
            </>
          ) : (
            <span className="text-[#9ca3af]">{activePage.title || 'Untitled'}</span>
          )}
        </div>
        
        <div className="relative">
          <div 
            className="cursor-pointer text-[#6b7280] hover:text-white transition-colors p-1 rounded hover:bg-white/10"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            <MoreHorizontal className="w-5 h-5" />
          </div>
          
          {isMenuOpen && (
            <div className="absolute top-[100%] right-0 mt-2 p-1.5 bg-[#0f0f13]/95 backdrop-blur-2xl border border-white/10 rounded-xl shadow-[0_15px_40px_rgba(0,0,0,0.8)] z-50 w-[200px] flex flex-col gap-0.5">
              <button 
                className="flex items-center gap-3 text-left px-3 py-2 text-[14px] text-[#d1d5db] hover:bg-white/10 hover:text-white rounded-md transition-colors"
                onClick={handleCopy}
              >
                <Copy className="w-4 h-4" />
                Copy page content
              </button>
              <button 
                className="flex items-center gap-3 text-left px-3 py-2 text-[14px] text-[#d1d5db] hover:bg-white/10 hover:text-white rounded-md transition-colors"
                onClick={() => {
                  onDuplicatePage?.(activePage.id);
                  setIsMenuOpen(false);
                }}
              >
                <CopyPlus className="w-4 h-4" />
                Duplicate
              </button>
              <button 
                className="flex items-center gap-3 text-left px-3 py-2 text-[14px] text-[#d1d5db] hover:bg-white/10 hover:text-white rounded-md transition-colors"
                onClick={handleExport}
              >
                <Download className="w-4 h-4" />
                Export
              </button>
              <div className="h-[1px] bg-[#666565]/50 my-1 mx-1" />
              <button 
                className="flex items-center gap-3 text-left px-3 py-2 text-[14px] text-red-400 hover:bg-red-400/10 hover:text-red-300 rounded-md transition-colors"
                onClick={() => {
                  onDeletePage?.(activePage.id);
                  setIsMenuOpen(false);
                }}
              >
                <Trash2 className="w-4 h-4" />
                Move to trash
              </button>
            </div>
          )}
        </div>
      </div>

      <div className=" mx-auto w-full group mt-[30px] relative">
        {/* Big Icon */}
        <div className="mb-6 mt-10 relative inline-block">
          <div 
            className="cursor-pointer hover:bg-white/10 p-2 rounded-lg transition-colors"
            onClick={() => setIsIconPickerOpen(!isIconPickerOpen)}
          >
            {activePage.icon ? (
              <span className="text-[42px] leading-none block">{activePage.icon}</span>
            ) : (
              <Pencil className="w-[42px] h-[42px] text-[#8b5cf6] fill-[#8b5cf6] -rotate-12" />
            )}
          </div>

          {/* Icon Picker Popover */}
          {isIconPickerOpen && (
            <div className="absolute top-[100%] left-0 mt-2 p-3 bg-[#0f0f13]/95 backdrop-blur-2xl border border-white/10 rounded-xl shadow-[0_15px_40px_rgba(0,0,0,0.8)] z-50 w-[260px]">
              <div className="text-xs font-semibold text-gray-400 mb-3 px-1 uppercase tracking-wider">Choose an icon</div>
              <div className="grid grid-cols-5 gap-2 max-h-[220px] overflow-y-auto custom-scrollbar">
                {emojis.map(emoji => (
                  <button
                    key={emoji}
                    className="text-2xl hover:bg-white/10 p-2 rounded-lg transition-colors flex items-center justify-center"
                    onClick={() => {
                      updatePage?.(activePage.id, { icon: emoji });
                      setIsIconPickerOpen(false);
                    }}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        
        {/* Title */}
        <input 
          type="text"
          value={activePage.title}
          onChange={(e) => updatePage?.(activePage.id, { title: e.target.value })}
          placeholder="Untitled"
          className={`w-full bg-transparent text-[44px] font-bold text-white placeholder-[#4b5563] outline-none ${subPages.length > 0 ? 'mb-6' : 'mb-8'}`}
        />

        {/* Content Area */}
        {editor && !editor.isActive('table') && (
          <BubbleMenu 
            editor={editor} 
            className="flex items-center gap-1.5 bg-[#0f0f13]/90 backdrop-blur-xl border border-white/10 p-1.5 rounded-full shadow-[0_10px_30px_rgba(0,0,0,0.5)] z-50 select-none relative"
          >
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleBold().run()}
              className={`p-2 rounded-full hover:bg-white/10 active:scale-95 transition-all duration-200 ${editor.isActive('bold') ? 'bg-purple-600/20 text-purple-400 border border-purple-500/20' : 'text-neutral-400 hover:text-white'}`}
            >
              <Bold className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleItalic().run()}
              className={`p-2 rounded-full hover:bg-white/10 active:scale-95 transition-all duration-200 ${editor.isActive('italic') ? 'bg-purple-600/20 text-purple-400 border border-purple-500/20' : 'text-neutral-400 hover:text-white'}`}
            >
              <Italic className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleUnderline().run()}
              className={`p-2 rounded-full hover:bg-white/10 active:scale-95 transition-all duration-200 ${editor.isActive('underline') ? 'bg-purple-600/20 text-purple-400 border border-purple-500/20' : 'text-neutral-400 hover:text-white'}`}
            >
              <Underline className="w-4 h-4" />
            </button>

            <div className="w-[1px] h-5 bg-white/10 mx-1.5" />

            {/* Text Color Button */}
            <div className="relative">
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  setShowTextColor(!showTextColor);
                  setShowHighlightColor(false);
                }}
                className={`p-2 rounded-full hover:bg-white/10 active:scale-95 transition-all duration-200 flex items-center gap-1 ${showTextColor ? 'bg-purple-600/20 text-purple-400 border border-purple-500/20' : 'text-neutral-400 hover:text-white'}`}
              >
                <Palette className="w-4 h-4" />
              </button>

              {showTextColor && (
                <div className="absolute bottom-[100%] left-1/2 -translate-x-1/2 mb-3.5 p-2 bg-[#0f0f13]/95 backdrop-blur-2xl border border-white/10 rounded-xl shadow-[0_10px_35px_rgba(0,0,0,0.8)] flex flex-col gap-1 min-w-[150px] max-h-[220px] overflow-y-auto z-[60] custom-scrollbar">
                  <div className="text-[11px] text-neutral-500 font-semibold px-2 py-1 select-none">TEXT COLOR</div>
                  {colors.map(color => (
                    <button
                      key={color.name}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                      }}
                      onClick={() => {
                        if (color.value === 'inherit') {
                          editor.chain().focus().unsetColor().run();
                        } else {
                          editor.chain().focus().setColor(color.value).run();
                        }
                        setShowTextColor(false);
                      }}
                      className="flex items-center gap-2.5 text-left px-2.5 py-2 text-[14px] rounded-lg hover:bg-white/10 transition-colors text-white w-full group"
                    >
                      <span className="w-4 h-4 rounded-full border border-white/15 shrink-0 transition-transform group-hover:scale-110" style={{ backgroundColor: color.value === 'inherit' ? 'transparent' : color.value }} />
                      <span className="font-light truncate text-neutral-200 group-hover:text-white">{color.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Highlight Color Button */}
            <div className="relative">
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  setShowHighlightColor(!showHighlightColor);
                  setShowTextColor(false);
                }}
                className={`p-2 rounded-full hover:bg-white/10 active:scale-95 transition-all duration-200 flex items-center gap-1 ${showHighlightColor ? 'bg-purple-600/20 text-purple-400 border border-purple-500/20' : 'text-neutral-400 hover:text-white'}`}
              >
                <Highlighter className="w-4 h-4" />
              </button>

              {showHighlightColor && (
                <div className="absolute bottom-[100%] left-1/2 -translate-x-1/2 mb-3.5 p-2 bg-[#0f0f13]/95 backdrop-blur-2xl border border-white/10 rounded-xl shadow-[0_10px_35px_rgba(0,0,0,0.8)] flex flex-col gap-1 min-w-[150px] max-h-[220px] overflow-y-auto z-[60] custom-scrollbar">
                  <div className="text-[11px] text-neutral-500 font-semibold px-2 py-1 select-none">HIGHLIGHT</div>
                  {highlights.map(hl => (
                    <button
                      key={hl.name}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                      }}
                      onClick={() => {
                        if (hl.value === 'transparent') {
                          editor.chain().focus().unsetHighlight().run();
                        } else {
                          editor.chain().focus().setHighlight({ color: hl.value }).run();
                        }
                        setShowHighlightColor(false);
                      }}
                      className="flex items-center gap-2.5 text-left px-2.5 py-2 text-[14px] rounded-lg hover:bg-white/10 transition-colors text-white w-full group"
                    >
                      <span className="w-4 h-4 rounded border border-white/15 shrink-0 transition-transform group-hover:scale-110" style={{ backgroundColor: hl.value }} />
                      <span className="font-light truncate text-neutral-200 group-hover:text-white">{hl.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </BubbleMenu>
        )}

        {editor && editor.isActive('table') && (
          <BubbleMenu 
            editor={editor} 
            className="flex items-center gap-1 bg-[#0f0f13]/95 backdrop-blur-xl border border-white/10 p-1.5 rounded-xl shadow-[0_15px_40px_rgba(0,0,0,0.7)] z-50 select-none relative"
          >
            <button
              type="button"
              onClick={() => editor.chain().focus().addColumnBefore().run()}
              className="px-2 py-1 text-xs rounded hover:bg-white/10 text-neutral-300 hover:text-white transition-colors"
              title="Add column before"
            >
              +Col L
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().addColumnAfter().run()}
              className="px-2 py-1 text-xs rounded hover:bg-white/10 text-neutral-300 hover:text-white transition-colors"
              title="Add column after"
            >
              +Col R
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().deleteColumn().run()}
              className="px-2 py-1 text-xs rounded hover:bg-red-400/20 text-red-400 transition-colors"
              title="Delete column"
            >
              -Col
            </button>
            <div className="w-[1px] h-4 bg-white/10 mx-1" />
            <button
              type="button"
              onClick={() => editor.chain().focus().addRowBefore().run()}
              className="px-2 py-1 text-xs rounded hover:bg-white/10 text-neutral-300 hover:text-white transition-colors"
              title="Add row before"
            >
              +Row A
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().addRowAfter().run()}
              className="px-2 py-1 text-xs rounded hover:bg-white/10 text-neutral-300 hover:text-white transition-colors"
              title="Add row after"
            >
              +Row B
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().deleteRow().run()}
              className="px-2 py-1 text-xs rounded hover:bg-red-400/20 text-red-400 transition-colors"
              title="Delete row"
            >
              -Row
            </button>
            <div className="w-[1px] h-4 bg-white/10 mx-1" />
            <button
              type="button"
              onClick={() => editor.chain().focus().deleteTable().run()}
              className="px-2 py-1 text-xs rounded hover:bg-red-500/20 text-red-400 font-semibold transition-colors"
              title="Delete table"
            >
              Delete Table
            </button>
          </BubbleMenu>
        )}

        {/* Global Drag Handle */}
        {editor && (
          <DragHandleComponent editor={editor} tippyOptions={{ zIndex: 9999, placement: 'left' }} className="flex items-center justify-start w-10 h-6 text-[#6b7280] hover:text-[#d1d5db] cursor-grab relative z-50 group">
            <div className="flex items-center justify-center w-7 h-7 hover:bg-white/10 rounded transition-colors ml-1">
              <GripVertical className="w-5 h-5" />
            </div>
          </DragHandleComponent>
        )}

        <EditorContent editor={editor} />
      </div>

      {/* Slash Command Suggestion Menu */}
      {slashQuery !== null && slashCoords && filteredItems.length > 0 && (
        <div 
          className="absolute bg-[#0f0f13]/95 backdrop-blur-2xl border border-white/10 rounded-xl shadow-[0_15px_40px_rgba(0,0,0,0.8)] p-2 z-[70] flex flex-col gap-0.5 max-h-[300px] overflow-y-auto w-[280px] custom-scrollbar"
          style={{ 
            top: `${slashCoords.top}px`, 
            left: `${slashCoords.left}px`,
          }}
        >
          <div className="text-[11px] text-neutral-500 font-semibold px-2.5 py-1.5 select-none uppercase tracking-wider">Basic Blocks</div>
          {filteredItems.map((item, idx) => {
            const isSelected = idx === selectedIndex;
            return (
              <button
                key={item.id}
                id={`slash-item-${idx}`}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                }}
                onClick={() => executeCommand(item)}
                className={`flex items-center gap-3 text-left px-2.5 py-2 rounded-lg transition-colors w-full group ${isSelected ? 'bg-purple-600/20 text-purple-400 border border-purple-500/20' : 'hover:bg-white/5 text-neutral-300 hover:text-white border border-transparent'}`}
              >
                <div className={`p-2 rounded-md transition-colors ${isSelected ? 'bg-purple-600/30' : 'bg-white/5 group-hover:bg-white/10'}`}>
                  {item.icon}
                </div>
                <div className="flex flex-col min-w-0">
                  <span className="text-[14px] font-medium leading-normal">{item.title}</span>
                  <span className="text-[11px] text-neutral-400 font-light truncate leading-normal">{item.description}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </main>
  );
};

export default ContentEditor;
