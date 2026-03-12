import React from 'react';
import Toolbar from './components/Toolbar';
import SheetCanvas from './components/SheetCanvas';
import GridControls from './components/GridControls';
import CategoryManager from './components/CategoryManager';
import SpriteProperties from './components/SpriteProperties';
import SpriteList from './components/SpriteList';
import PreviewPanel from './components/PreviewPanel';
import AnimationEditor from './components/AnimationEditor';
import './App.css';

export default function App() {
  return (
    <div className="app">
      <Toolbar />
      <div className="main-layout">
        <div className="canvas-area">
          <SheetCanvas />
        </div>
        <div className="sidebar">
          <div className="sidebar-scroll">
            <GridControls />
            <SpriteProperties />
            <PreviewPanel />
            <CategoryManager />
            <AnimationEditor />
            <SpriteList />
          </div>
        </div>
      </div>
    </div>
  );
}
