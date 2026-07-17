"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { Menu, Home, Search, ChevronDown, ChevronRight, Pencil, Settings, Trash, Plus, LogOut, Sparkles, User as UserIcon } from "lucide-react";
import { PageItem } from "@/app/dashboard/DashboardContent";
import type { User } from "@supabase/supabase-js";
import { toast } from "sonner";

type SidebarProps = {
  pages?: PageItem[];
  activePageId?: string;
  activeView?: "home" | "page" | "settings" | "trash";
  onSelectPage?: (id: string) => void;
  onSelectHome?: () => void;
  onOpenSearch?: () => void;
  onOpenSettings?: () => void;
  onAddPage?: (parentId: string | null, preventSwitch?: boolean) => string | void;
  onTogglePage?: (id: string) => void;
  onDeletePage?: (id: string) => void;
  user?: User;
  onLogout?: () => void;
};

const PageTreeItem = ({ 
  page, 
  allPages, 
  depth = 0,
  activePageId,
  onSelectPage,
  onAddPage,
  onTogglePage,
  onDeletePage
}: { 
  page: PageItem, 
  allPages: PageItem[], 
  depth?: number,
  activePageId?: string;
  onSelectPage?: (id: string) => void;
  onAddPage?: (parentId: string | null, preventSwitch?: boolean) => string | void;
  onTogglePage?: (id: string) => void;
  onDeletePage?: (id: string) => void;
}) => {
  const children = allPages.filter(p => p.parentId === page.id);
  const hasChildren = children.length > 0;
  const isActive = activePageId === page.id;

  return (
    <div className="flex flex-col">
      <div 
        className={`group flex items-center gap-1 cursor-pointer transition-colors py-1.5 pr-2 rounded-md ${isActive ? 'bg-white/10 text-white' : 'text-[#d1d5db] hover:bg-white/5 hover:text-white'}`}
        style={{ paddingLeft: `${depth * 16}px` }}
        onClick={() => onSelectPage?.(page.id)}
      >
        <div 
          className="flex items-center justify-center w-5 h-5 opacity-70 hover:opacity-100 hover:bg-white/10 rounded ml-1"
          onClick={(e) => {
            e.stopPropagation();
            onTogglePage?.(page.id);
          }}
        >
          {hasChildren ? (
            page.isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />
          ) : (
             <div className="w-4 h-4" />
          )}
        </div>
        
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {page.icon ? (
            <span className="text-[16px] leading-none shrink-0">{page.icon}</span>
          ) : (
            <Pencil className="w-[16px] h-[16px] text-[#8b5cf6] fill-[#8b5cf6] shrink-0" />
          )}
          <span className="text-[15px] font-light truncate">{page.title || 'Untitled'}</span>
        </div>

        {/* Actions on hover */}
        <div className="opacity-0 group-hover:opacity-100 flex items-center pr-1 gap-0.5">
          <div 
            className="p-1 hover:bg-white/10 rounded transition-all text-[#9ca3af] hover:text-white"
            onClick={(e) => {
              e.stopPropagation();
              onDeletePage?.(page.id);
            }}
          >
            <Trash className="w-[13px] h-[13px]" />
          </div>
          <div 
            className="p-1 hover:bg-white/10 rounded transition-all text-[#9ca3af] hover:text-white"
            onClick={(e) => {
              e.stopPropagation();
              onAddPage?.(page.id);
            }}
          >
            <Plus className="w-[14px] h-[14px]" />
          </div>
        </div>
      </div>
      
      {page.isOpen && hasChildren && (
        <div className="flex flex-col mt-0.5">
          {children.map(child => (
            <PageTreeItem 
              key={child.id} 
              page={child} 
              allPages={allPages} 
              depth={depth + 1}
              activePageId={activePageId}
              onSelectPage={onSelectPage}
              onAddPage={onAddPage}
              onTogglePage={onTogglePage}
              onDeletePage={onDeletePage}
            />
          ))}
        </div>
      )}
    </div>
  );
}

const Sidebar = ({
  pages = [],
  activePageId,
  activeView,
  onSelectPage,
  onSelectHome,
  onOpenSearch,
  onOpenSettings,
  onAddPage,
  onTogglePage,
  onDeletePage,
  user,
  onLogout
}: SidebarProps) => {
  const router = useRouter();
  const [isPinned, setIsPinned] = useState(true);
  const [isHovered, setIsHovered] = useState(false);
  const [isPagesOpen, setIsPagesOpen] = useState(true);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // Root pages are those without a parentId
  const rootPages = pages.filter(p => !p.parentId);

  return (
    <>
      {!isPinned && (
        <div 
          className="absolute left-0 top-0 h-full w-[30px] z-40"
          onMouseEnter={() => setIsHovered(true)}
        />
      )}

      <aside 
        className={`
          flex flex-col shrink-0
          border border-[#666565]/50 rounded-lg h-[calc(100vh-40px)] text-white
          transition-all duration-300 ease-in-out z-50 py-[29px] bg-background/20 backdrop-blur-sm px-2
          ${
            isPinned
              ? "my-[20px] ml-[20px] w-[336px] relative"
              : "absolute top-[20px] left-[20px] w-[366px] shadow-[0_0_20px_rgba(0,0,0,0.5)] bg-[#06060a]"
          }
          ${
            !isPinned && !isHovered
              ? "-translate-x-[calc(100%+40px)] opacity-0 pointer-events-none"
              : "translate-x-0 opacity-100 pointer-events-auto"
          }
        `}
        onMouseEnter={() => !isPinned && setIsHovered(true)}
        onMouseLeave={() => !isPinned && setIsHovered(false)}
      >
        <div className="flex items-center px-[34px]">
          <div className="flex-1">
            <Link href="/">
              <Image
                src="/icons/logo.svg"
                alt="Learner Logo"
                width={130}
                height={33.39}
                className="cursor-pointer"
              />
            </Link>
          </div>
          <div
            className="cursor-pointer hover:text-text-primary text-text-secondary transition-colors"
            onClick={() => {
              setIsPinned(!isPinned);
              setIsHovered(false);
            }}
          >
            <Menu />
          </div>
        </div>

        <div className="flex flex-col gap-6 mt-8 px-[34px]">
          <div
            className={`flex items-center gap-4 cursor-pointer transition-colors ${activeView === "home" ? "text-white" : "text-[#d1d5db] hover:text-white"}`}
            onClick={onSelectHome}
          >
            <Home className="w-[20px] h-[20px]" strokeWidth={1.5} />
            <span className="font-light tracking-wide">Home</span>
          </div>
          <div
            className="flex items-center gap-4 cursor-pointer text-[#d1d5db] hover:text-white transition-colors"
            onClick={onOpenSearch}
          >
            <Search className="w-[20px] h-[20px]" strokeWidth={1.5} />
            <span className="font-light tracking-wide">Search</span>
          </div>
        </div>

        <div className="flex flex-col flex-1 mt-8 px-[26px]">
          <div className="flex items-center justify-between text-[#9ca3af] group px-2">
            <div 
              className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors"
              onClick={() => setIsPagesOpen(!isPagesOpen)}
            >
              <span className="text-[16px] font-light">Pages</span>
              {isPagesOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </div>
            
            <div 
              className="cursor-pointer p-1 opacity-0 group-hover:opacity-100 hover:bg-white/10 hover:text-white rounded transition-all"
              onClick={() => onAddPage?.(null)}
            >
              <Plus className="w-[18px] h-[18px]" />
            </div>
          </div>
          
          <div 
            className={`flex flex-col gap-2 overflow-y-auto scrollbar-hide transition-all duration-300 ease-in-out ${
              isPagesOpen ? "h-full mt-4 opacity-100" : "max-h-0 mt-0 opacity-0 "
            }`}
          >
            {rootPages.map(page => (
              <PageTreeItem 
                key={page.id}
                page={page}
                allPages={pages}
                activePageId={activePageId}
                onSelectPage={onSelectPage}
                onAddPage={onAddPage}
                onTogglePage={onTogglePage}
                onDeletePage={onDeletePage}
              />
            ))}
          </div>
        </div>

        <div className="mt-auto px-[20px] pb-4 flex flex-col">
          {isProfileOpen && (
            <div className="mb-2 bg-zinc-900 border border-zinc-800 rounded-xl p-1.5 shadow-2xl flex flex-col gap-0.5 text-sm animate-in fade-in slide-in-from-bottom-2">
              <div className="px-3 py-2 border-b border-zinc-800/80 mb-1 flex items-center gap-2">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary font-semibold text-sm">
                  {user?.email?.[0].toUpperCase() || "U"}
                </div>
                <div className="flex flex-col min-w-0">
                  <span className="text-zinc-200 font-semibold truncate text-[13px]">
                    {user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email?.split('@')[0] || "User"}
                  </span>
                  <span className="text-zinc-500 text-[11px] truncate">{user?.email}</span>
                </div>
              </div>

              <button 
                className="flex items-center gap-3 px-3 py-2 text-zinc-300 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer w-full text-left"
                onClick={() => {
                  router.push("/pricing");
                  setIsProfileOpen(false);
                }}
              >
                <Sparkles className="w-4 h-4 text-primary" />
                <span>Upgrade plan</span>
              </button>

              <button 
                className="flex items-center gap-3 px-3 py-2 text-zinc-300 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer w-full text-left"
                onClick={() => {
                  onOpenSettings?.();
                  setIsProfileOpen(false);
                }}
              >
                <Settings className="w-4 h-4 text-zinc-400" />
                <span>Settings</span>
              </button>

              <button 
                className={`flex items-center gap-3 px-3 py-2 ${activeView === "trash" ? "text-white bg-zinc-800" : "text-zinc-300"} hover:text-white hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer w-full text-left`}
                onClick={() => {
                  router.push("/dashboard/trash");
                  setIsProfileOpen(false);
                }}
              >
                <Trash className="w-4 h-4 text-zinc-400" />
                <span>Trash</span>
              </button>
              
              <div className="h-px bg-zinc-800/80 my-1"></div>

              <button 
                className="flex items-center gap-3 px-3 py-2 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer w-full text-left"
                onClick={() => {
                  setIsProfileOpen(false);
                  onLogout?.();
                }}
              >
                <LogOut className="w-4 h-4" />
                <span>Log out</span>
              </button>
            </div>
          )}

          <div 
            className="flex items-center gap-3 cursor-pointer hover:bg-white/5 p-2 rounded-xl transition-colors"
            onClick={() => setIsProfileOpen(!isProfileOpen)}
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary font-bold text-sm">
              {user?.email?.[0].toUpperCase() || "U"}
            </div>
            <span className="text-[15px] font-medium text-zinc-200 truncate select-none">
              {user?.user_metadata?.full_name || user?.user_metadata?.name || user?.email?.split('@')[0] || "User"}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
